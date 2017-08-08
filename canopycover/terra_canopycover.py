#!/usr/bin/env python

import os
import logging
import time

from pyclowder.utils import CheckMessage
from pyclowder.datasets import download_metadata, upload_metadata
from pyclowder.files import upload_to_dataset
from terrautils.metadata import get_extractor_metadata, get_terraref_metadata
from terrautils.extractors import TerrarefExtractor, is_latest_file, load_json_file, \
    create_geotiff, create_image, calculate_gps_bounds, calculate_centroid, \
    calculate_scan_time, build_metadata
from terrautils.betydb import get_sites_by_latlon, submit_traits
from terrautils.geostreams import create_datapoint_with_dependencies

import canopyCover as ccCore


def add_local_arguments(parser):
    # add any additional arguments to parser

    self.parser.add_argument('--betyURL', dest="bety_url", type=str, nargs='?',
                             default="https://terraref.ncsa.illinois.edu/bety/api/beta/traits.csv",
                             help="traits API endpoint of BETY instance that outputs should be posted to")
    self.parser.add_argument('--betyKey', dest="bety_key", type=str, nargs='?', default=bety_key,
                             help="API key for BETY instance specified by betyURL")

class CanopyCoverHeight(TerrarefExtractor):
    def __init__(self):
        super(CanopyCoverHeight, self).__init__()

        # parse command line and load default logging configuration
        self.setup(sensor='stereoTop_canopyCover')

        # assign other argumentse
        self.bety_url = self.args.bety_url
        self.bety_key = self.args.bety_key

    def check_message(self, connector, host, secret_key, resource, parameters):
        # TODO: Consider if this should be run on a fullfield mosaic and iterate across all plots to clip + analyze

        if not is_latest_file(resource):
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
            timestamp = resource['dataset_info']['name'].split(" - ")[1]
            out_csv = self.sensors.get_sensor_path(timestamp, opts=['canopycover'], ext='csv')
            if os.path.isfile(out_csv):
                logging.info("skipping dataset %s, output already exists" % resource['id'])
                return CheckMessage.ignore

        # fetch metadata from dataset to check if we should remove existing entry for this extractor first
        md = download_metadata(connector, host, secret_key, resource['id'])
        if get_extractor_metadata(md, self.extractor_info['name']) and not self.force_overwrite:
            logging.info("skipping dataset %s, metadata already exists" % resource['id'])
            return CheckMessage.ignore
        if get_terraref_metadata(md) and found_left and found_right:
            return CheckMessage.download
        return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message()

        # Get left/right files and metadata
        img_left, img_right, metadata = None, None, None
        for fname in resource['local_paths']:
            # First check metadata attached to dataset in Clowder for item of interest
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = load_json_file(fname)
                metadata = get_extractor_metadata(all_dsmd)
            # Otherwise, check if metadata was uploaded as a .json file
            elif fname.endswith('_metadata.json') and fname.find('/_metadata.json') == -1 and metadata is None:
                metadata = load_json_file(fname)
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [img_left, img_right, metadata]:
            raise ValueError("could not locate each of left+right+metadata in processing")

        # Determine output directory
        timestamp = resource['dataset_info']['name'].split(" - ")[1]
        out_csv = self.sensors.get_sensor_path(timestamp, opts=['canopycover'], ext='csv')
        out_dir = os.path.dirname(out_csv)
        self.sensors.create_sensor_path(out_dir)

        # Get location information from input data
        metadata = ccCore.lower_keys(metadata)
        left_bounds = calculate_gps_bounds(metadata)[0]
        sensor_latlon = calculate_centroid(left_bounds)
        logging.info("sensor lat/lon: %s" % str(sensor_latlon))

        if (not os.path.isfile(out_csv)) or self.force_overwrite:
            # TODO: Get plot from BETYdb filtered by season
            plots = get_sites_by_latlon(sensor_latlon)
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

            self.created += 1
            self.bytes += os.path.getsize(out_csv)

        # Only upload the newly generated CSV to Clowder if it isn't already in dataset
        if out_csv not in resource['local_paths']:
            csv_id = upload_to_dataset(connector, host, secret_key, resource['id'], out_csv)
        else:
            csv_id = ""

        # submit CSV to BETY
        submit_traits(out_csv, self.bety_key)

        # Prepare and submit datapoint
        fileIdList = []
        for f in resource['files']:
            fileIdList.append(f['id'])
        # Format time properly, adding UTC if missing from Danforth timestamp
        ctime = calculate_scan_time(metadata)
        time_obj = time.strptime(ctime, "%m/%d/%Y %H:%M:%S")
        time_fmt = time.strftime('%Y-%m-%dT%H:%M:%S', time_obj)
        if len(time_fmt) == 19:
            time_fmt += "-06:00"

        dpmetadata = {
            "source": host+"datasets/"+resource['id'],
            "file_ids": ",".join(fileIdList),
            "canopy_cover": ccVal
        }
        create_datapoint_with_dependencies(connector, host, secret_key, "Canopy Cover",
                                           sensor_latlon, time_fmt, time_fmt, dpmetadata)

        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        metadata = build_metadata(host, self.extractor_info['name'], resource['id'], {
            "files_created": [csv_id],
            "canopy_cover": ccVal
        }, 'dataset')
        upload_metadata(connector, host, secret_key, resource['id'], metadata)

        self.end_message()

if __name__ == "__main__":
    extractor = CanopyCoverHeight()
    extractor.start()
