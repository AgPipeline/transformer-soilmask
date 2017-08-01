#!/usr/bin/env python

import os
import logging
import time
import datetime

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
import pyclowder.datasets
import terrautils.geostreams
import terrautils.extractors
import terrautils.betydb

import canopyCover as ccCore


class CanopyCoverHeight(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        bety_key = os.getenv("BETYDB_KEY", False)
        influx_host = os.getenv("INFLUXDB_HOST", "terra-logging.ncsa.illinois.edu")
        influx_port = os.getenv("INFLUXDB_PORT", 8086)
        influx_db = os.getenv("INFLUXDB_DB", "extractor_db")
        influx_user = os.getenv("INFLUXDB_USER", "terra")
        influx_pass = os.getenv("INFLUXDB_PASSWORD", "")

        # add any additional arguments to parser
        # self.parser.add_argument('--max', '-m', type=int, nargs='?', default=-1,
        #                          help='maximum number (default=-1)')
        self.parser.add_argument('--overwrite', dest="force_overwrite", type=bool, nargs='?', default=False,
                                 help="whether to overwrite output file if it already exists in output directory")
        self.parser.add_argument('--betyURL', dest="bety_url", type=str, nargs='?',
                                 default="https://terraref.ncsa.illinois.edu/bety/api/beta/traits.csv",
                                 help="traits API endpoint of BETY instance that outputs should be posted to")
        self.parser.add_argument('--betyKey', dest="bety_key", type=str, nargs='?', default=bety_key,
                                 help="API key for BETY instance specified by betyURL")
        self.parser.add_argument('--plots', dest="plots_shp", type=str, nargs='?',
                                 default="/home/extractor/shp/sorghumexpfall2016v5/sorghumexpfall2016v5_lblentry_1to7.shp",
                                 help=".shp file containing plots")
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
        self.force_overwrite = self.args.force_overwrite
        self.bety_url = self.args.bety_url
        self.bety_key = self.args.bety_key
        self.plots_shp = self.args.plots_shp
        self.influx_params = {
            "host": self.args.influx_host,
            "port": self.args.influx_port,
            "db": self.args.influx_db,
            "user": self.args.influx_user,
            "pass": self.args.influx_pass
        }

    def check_message(self, connector, host, secret_key, resource, parameters):
        # TODO: Consider if this should be run on a fullfield mosaic and iterate across all plots to clip + analyze
        
        if not terrautils.extractors.is_latest_file(resource):
            return CheckMessage.ignore

        # Check for a left and right file before beginning processing
        found_left = False
        found_right = False
        for f in resource['files']:
            if 'filename' in f and f['filename'].endswith('_left.bin'):
                found_left = True
            elif 'filename' in f and f['filename'].endswith('_right.bin'):
                found_right = True
        if not (found_left and found_right):
            return CheckMessage.ignore

        # Check if output already exists
        if not self.force_overwrite:
            out_csv = terrautils.sensors.get_sensor_path_by_dataset("ua-mac", "Level_1", resource['dataset_info']['name'],
                                                                    "stereoTop_canopyCover", 'csv', opts=['canopycover'])
            if os.path.isfile(out_csv):
                logging.info("skipping dataset %s, output already exists" % resource['id'])
                return CheckMessage.ignore

        # fetch metadata from dataset to check if we should remove existing entry for this extractor first
        md = pyclowder.datasets.download_metadata(connector, host, secret_key, resource['id'])
        found_meta = False
        for m in md:
            if 'agent' in m and 'name' in m['agent']:
                if m['agent']['name'].find(self.extractor_info['name']) > -1:
                    logging.info("skipping dataset %s, metadata already exists" % resource['id'])
                    return CheckMessage.ignore
            # Check for required metadata before beginning processing
            if 'content' in m and 'lemnatec_measurement_metadata' in m['content']:
                found_meta = True

        if found_left and found_right and found_meta:
            return CheckMessage.download
        else:
            return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        starttime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        created = 0
        bytes = 0

        # Get left/right files and metadata
        img_left, img_right, metadata = None, None, None
        for fname in resource['local_paths']:
            # First check metadata attached to dataset in Clowder for item of interest
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = terrautils.extractors.load_json_file(fname)
                for curr_dsmd in all_dsmd:
                    if 'content' in curr_dsmd and 'lemnatec_measurement_metadata' in curr_dsmd['content']:
                        metadata = curr_dsmd['content']
            # Otherwise, check if metadata was uploaded as a .json file
            elif fname.endswith('_metadata.json') and fname.find('/_metadata.json') == -1 and metadata is None:
                metadata = terrautils.extractors.load_json_file(fname)
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [img_left, img_right, metadata]:
            raise ValueError("could not locate each of left+right+metadata in processing")

        # Determine output directory
        out_csv = terrautils.sensors.get_sensor_path_by_dataset("ua-mac", "Level_1", resource['dataset_info']['name'],
                                                                "stereoTop_canopyCover", 'csv', opts=['canopycover'])
        out_dir = os.path.dirname(out_csv)
        logging.info("...writing outputs to: %s" % out_dir)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        # Get location information from input data
        metadata = ccCore.lower_keys(metadata)
        left_bounds = terrautils.extractors.calculate_gps_bounds(metadata)[0]
        sensor_latlon = terrautils.extractors.calculate_centroid(left_bounds)
        logging.info("sensor lat/lon: %s" % str(sensor_latlon))

        if (not os.path.isfile(out_csv)) or self.force_overwrite:
            # TODO: Get plot from BETYdb filtered by season
            plots = terrautils.betydb.get_sites_by_latlon(sensor_latlon)
            plot_name = "Unknown"
            for p in plots:
                plot_name = p['sitename']
                continue

            # get traits and values & generate output CSV
            ccVal = ccCore.get_CC_from_bin(img_left)
            (fields, traits) = ccCore.get_traits_table()
            traits['canopy_cover'] = str(ccVal)

            str_time = str(ccCore.get_localdatetime(metadata))
            str_date = str_time[6:10]+'-'+str_time[:5]+'T'+str_time[11:]
            traits['local_datetime'] = str_date.replace("/", '-')
            traits['site'] = plot_name
            trait_list = ccCore.generate_traits_list(traits)
            ccCore.generate_cc_csv(out_csv, fields, trait_list)

            created += 1
            bytes += os.path.getsize(out_csv)

        # Only upload the newly generated CSV to Clowder if it isn't already in dataset
        if out_csv not in resource['local_paths']:
            csv_id = pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], out_csv)
        else:
            csv_id = ""

        # submit CSV to BETY
        terrautils.betydb.submit_traits(out_csv, self.bety_key)

        # Prepare and submit datapoint
        fileIdList = []
        for f in resource['files']:
            fileIdList.append(f['id'])
        # Format time properly, adding UTC if missing from Danforth timestamp
        ctime = terrautils.extractors.calculate_scan_time(metadata)
        time_obj = time.strptime(ctime, "%m/%d/%Y %H:%M:%S")
        time_fmt = time.strftime('%Y-%m-%dT%H:%M:%S', time_obj)
        if len(time_fmt) == 19:
            time_fmt += "-06:00"

        dpmetadata = {
            "source": host+"datasets/"+resource['id'],
            "file_ids": ",".join(fileIdList),
            "canopy_cover": ccVal
        }
        terrautils.geostreams.create_datapoint_with_dependencies(connector, host, secret_key,
                                                                 "Canopy Cover", sensor_latlon,
                                                                 time_fmt, time_fmt, dpmetadata)

        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        metadata = terrautils.extractors.build_metadata(host, self.extractor_info['name'], resource['id'], {
            "files_created": [csv_id],
            "canopy_cover": ccVal
        }, 'dataset')
        pyclowder.datasets.upload_metadata(connector, host, secret_key, resource['id'], metadata)

        endtime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        terrautils.extractors.log_to_influxdb(self.extractor_info['name'], self.influx_params,
                                              starttime, endtime, created, bytes)


if __name__ == "__main__":
    extractor = CanopyCoverHeight()
    extractor.start()
