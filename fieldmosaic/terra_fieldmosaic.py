#!/usr/bin/env python

import os
import logging
import requests
import subprocess

import datetime
from dateutil.parser import parse
from influxdb import InfluxDBClient, SeriesHelper

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
import pyclowder.datasets
import terrautils.extractors

import full_day_to_tiles
import shadeRemoval as shade


class FullFieldMosaicStitcher(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        influx_host = os.getenv("INFLUXDB_HOST", "terra-logging.ncsa.illinois.edu")
        influx_port = os.getenv("INFLUXDB_PORT", 8086)
        influx_db = os.getenv("INFLUXDB_DB", "extractor_db")
        influx_user = os.getenv("INFLUXDB_USER", "terra")
        influx_pass = os.getenv("INFLUXDB_PASSWORD", "")

        # add any additional arguments to parser
        self.parser.add_argument('--output', '-o', dest="output_dir", type=str, nargs='?',
                                 default="/home/extractor/sites/ua-mac/Level_1/fullfield",
                                 help="root directory where timestamp & output directories will be created")
        self.parser.add_argument('--overwrite', dest="force_overwrite", type=bool, nargs='?', default=False,
                                 help="whether to overwrite output file if it already exists in output directory")
        self.parser.add_argument('--mainspace', dest="mainspace", type=str, nargs='?',
                                 default="58da6b924f0c430e2baa823f", help="Space UUID in Clowder to store results")
        self.parser.add_argument('--darker', dest="generate_darker", type=bool, nargs='?', default=False,
                                 help="whether to use multipass mosiacking to select darker pixels")
        self.parser.add_argument('--split', dest="split_num", type=int, nargs='?', default=2,
                                 help="number of splits to use if --darker is True")
        self.parser.add_argument('--influxHost', dest="influx_host", type=str, nargs='?',
                                 default=influx_host, help="InfluxDB URL for logging")
        self.parser.add_argument('--influxPort', dest="influx_port", type=int, nargs='?',
                                 default=influx_port, help="InfluxDB port")
        self.parser.add_argument('--influxUser', dest="influx_user", type=str, nargs='?',
                                 default=influx_user, help="InfluxDB username")
        self.parser.add_argument('--influxPass', dest="influx_pass", type=str, nargs='?',
                                 default=influx_pass, help="InfluxDB password")
        self.parser.add_argument('--influxDB', dest="influx_db", type=str, nargs='?',
                                 default=influx_db, help="InfluxDB database")

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the exctractor
        logging.getLogger('pyclowder').setLevel(logging.DEBUG)
        logging.getLogger('__main__').setLevel(logging.DEBUG)

        # assign other arguments
        self.output_dir = self.args.output_dir
        self.force_overwrite = self.args.force_overwrite
        self.mainspace = self.args.mainspace
        self.generate_darker = self.args.generate_darker
        self.split_num = self.args.split_num
        self.influx_params = {
            "host": self.args.influx_host,
            "port": self.args.influx_port,
            "db": self.args.influx_db,
            "user": self.args.influx_user,
            "pass": self.args.influx_pass
        }

    def check_message(self, connector, host, secret_key, resource, parameters):
        return CheckMessage.bypass

    def process_message(self, connector, host, secret_key, resource, parameters):
        starttime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        created = 0
        bytes = 0

        # parameters["output_dataset"] = "Full Field - 2017-01-01"
        out_dir = terrautils.extractors.get_output_directory(self.soutput_dir, parameters["output_dataset"])
        out_root = terrautils.extractors.get_output_filename(parameters["output_dataset"], opts=["fullField"])
        out_vrt = os.path.join(out_dir, out_root+".vrt")
        out_tif_full = os.path.join(out_dir, out_root+".tif")
        out_tif_thumb = os.path.join(out_dir, out_root+"_thumb.tif")

        nu_created, nu_bytes = 0, 0
        if not self.generate_darker:
            (nu_created, nu_bytes) = self.generateSingleMosaic(out_dir, out_vrt, out_tif_thumb, out_tif_full, parameters)
        else:
            (nu_created, nu_bytes) = self.generateDarkerMosaic(out_dir, out_vrt, out_tif_thumb, out_tif_full, parameters)
        created += nu_created
        bytes += nu_bytes

        # Upload full field image to Clowder
        parent_collect = self.getCollectionOrCreate(connector, host, secret_key, "Full Field Stitched Mosaics",
                                                    parent_space=self.mainspace)
        year_collect = self.getCollectionOrCreate(connector, host, secret_key, parameters["output_dataset"][:17],
                                                  parent_collect, self.mainspace)
        month_collect = self.getCollectionOrCreate(connector, host, secret_key, parameters["output_dataset"][:20],
                                                   year_collect, self.mainspace)
        target_dsid = self.getDatasetOrCreate(connector, host, secret_key, parameters["output_dataset"],
                                              month_collect, self.mainspace)

        thumbid = pyclowder.files.upload_to_dataset(connector, host, secret_key, target_dsid, out_tif_thumb)
        fullid = pyclowder.files.upload_to_dataset(connector, host, secret_key, target_dsid, out_tif_full)

        content = {
            "comment": "This stitched image is computed based on an assumption that the scene is planar. \
                There are likely to be be small offsets near the boundary of two images anytime there are plants \
                at the boundary (because those plants are higher than the ground plane), or where the dirt is \
                slightly higher or lower than average.",
            "file_ids": parameters["file_ids"]
        }
        thumbmeta = terrautils.extractors.build_metadata(host, self.extractor_info['name'], thumbid, content, 'file')
        pyclowder.files.upload_metadata(connector, host, secret_key, thumbid, thumbmeta)
        fullmeta = terrautils.extractors.build_metadata(host, self.extractor_info['name'], fullid, content, 'file')
        pyclowder.files.upload_metadata(connector, host, secret_key, thumbid, fullmeta)

        endtime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        terrautils.extractors.log_to_influxdb(self.extractor_info['name'], self.influx_params,
                                              starttime, endtime, created, bytes)

    def getCollectionOrCreate(self, connector, host, secret_key, cname, parent_colln=None, parent_space=None):
        # Fetch dataset from Clowder by name, or create it if not found
        url = "%sapi/collections?key=%s&title=" % (host, secret_key, cname)
        result = requests.get(url, verify=connector.ssl_verify)
        result.raise_for_status()

        if len(result.json()) == 0:
            return pyclowder.collections.create_empty(connector, host, secret_key, cname, "",
                                                      parent_colln, parent_space)
        else:
            return result.json()[0]['id']

    def getDatasetOrCreate(self, connector, host, secret_key, dsname, parent_colln=None, parent_space=None):
        # Fetch dataset from Clowder by name, or create it if not found
        url = "%sapi/datasets?key=%s&title=" % (host, secret_key, dsname)
        result = requests.get(url, verify=connector.ssl_verify)
        result.raise_for_status()

        if len(result.json()) == 0:
            return pyclowder.datasets.create_empty(connector, host, secret_key, dsname, "",
                                                   parent_colln, parent_space)
        else:
            return result.json()[0]['id']

    def generateSingleMosaic(self, out_dir, out_vrt, out_tif_thumb, out_tif_full, parameters):
        # Create simple mosaic from geotiff list
        created, bytes = 0, 0

        if (not os.path.isfile(out_vrt)) or self.force_overwrite:
            logging.info("processing %s TIFs" % len(parameters['file_ids']))

            # Write input list to tmp file
            with open("tiflist.txt", "w") as tifftxt:
                for t in parameters["file_ids"]:
                    tifftxt.write("%s/n" % t)

            # Create VRT from every GeoTIFF
            logging.info("Creating %s..." % out_vrt)
            full_day_to_tiles.createVrtPermanent(out_dir, "tiflist.txt", out_vrt)
            os.remove("tiflist.txt")
            created += 1
            bytes += os.path.getsize(out_vrt)

        if (not os.path.isfile(out_tif_thumb)) or self.force_overwrite:
            # Convert VRT to full-field GeoTIFF (low-res then high-res)
            logging.info("Converting VRT to %s..." % out_tif_thumb)
            subprocess.call(["gdal_translate -projwin -111.9750277 33.0764277 -111.9748097 33.0745861 "+
                             "-outsize 10% 10% %s %s" % (out_vrt, out_tif_thumb)])
            created += 1
            bytes += os.path.getsize(out_tif_thumb)

        if (not os.path.isfile(out_tif_full)) or self.force_overwrite:
            logging.info("Converting VRT to %s..." % out_tif_full)
            subprocess.call(["gdal_translate -projwin -111.9750277 33.0764277 -111.9748097 33.0745861 "+
                             "%s %s" % (out_vrt, out_tif_full)])
            created += 1
            bytes += os.path.getsize(out_tif_full)

        return (created, bytes)

    def generateDarkerMosaic(self, out_dir, out_vrt, out_tif_thumb, out_tif_full, parameters):
        # Create dark-pixel mosaic from geotiff list using multipass for darker pixel selection
        created, bytes = 0, 0

        if (not os.path.isfile(out_vrt)) or self.force_overwrite:
            # Write input list to tmp file
            with open("tiflist.txt", "w") as tifftxt:
                for t in parameters["file_ids"]:
                    tifftxt.write("%s/n" % t)

            # Split full tiflist into parts according to split number
            shade.split_tif_list("tiflist.txt", out_dir, self.split_num)
            os.remove("tiflist.txt")

            # Generate tiles from each split VRT into numbered folders
            shade.create_diff_tiles_set(out_dir, self.split_num)

            # Choose darkest pixel from each overlapping tile
            unite_tiles_dir = os.path.join(out_dir, 'unite')
            shade.integrate_tiles(out_dir, unite_tiles_dir, self.split_num)

            # If any files didn't have overlap, copy individual tile
            shade.copy_missing_tiles(out_dir, unite_tiles_dir, self.split_num, tiles_folder_name='tiles_left')

            # Create output VRT from overlapped tiles
            # TODO: Adjust this step so google HTML isn't generated?
            shade.create_unite_tiles(unite_tiles_dir, out_vrt)
            created += 1
            bytes += os.path.getsize(out_vrt)

        if (not os.path.isfile(out_tif_thumb)) or self.force_overwrite:
            # Convert VRT to full-field GeoTIFF (low-res then high-res)
            logging.info("Converting VRT to %s..." % out_tif_thumb)
            subprocess.call(["gdal_translate -projwin -111.9750277 33.0764277 -111.9748097 33.0745861 "+
                             "-outsize 10% 10% %s %s" % (out_vrt, out_tif_thumb)])
            created += 1
            bytes += os.path.getsize(out_tif_thumb)

        if (not os.path.isfile(out_tif_full)) or self.force_overwrite:
            logging.info("Converting VRT to %s..." % out_tif_full)
            subprocess.call(["gdal_translate -projwin -111.9750277 33.0764277 -111.9748097 33.0745861 "+
                             "%s %s" % (out_vrt, out_tif_full)])
            created += 1
            bytes += os.path.getsize(out_tif_full)

        return (created, bytes)


if __name__ == "__main__":
    extractor = FullFieldMosaicStitcher()
    extractor.start()
