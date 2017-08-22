#!/usr/bin/env python

"""
This extractor will trigger when an image is uploaded into Clowder.

It will create csv file which contains the feature vectors.
"""

import os
import logging
import subprocess

from pyclowder.utils import CheckMessage
from pyclowder.datasets import get_info, upload_metadata
from pyclowder.files import upload_to_dataset
from terrautils.extractors import TerrarefExtractor, build_dataset_hierarchy, build_metadata
from terrautils.sensors import Sensors


class gift(TerrarefExtractor):
    def __init__(self):
        super(gift, self).__init__()

        # parse command line and load default logging configuration
        self.setup(sensor='texture_analysis')

    def check_message(self, connector, host, secret_key, resource, parameters):
        print("check msg")
        ds_md = get_info(connector, host, secret_key, resource['parent']['id'])

        s = Sensors('', 'ua-mac', 'rgb_geotiff')
        if ds_md['name'].find(s.get_display_name()) > -1:
            timestamp = ds_md['name'].split(" - ")[1]
            side = 'left' if resource['name'].find("_left") > -1 else 'right'
            out_csv = self.sensors.get_sensor_path(timestamp, opts=[side], ext='csv')
            print(out_csv)
            if not os.path.exists(out_csv) or self.overwrite:
                return CheckMessage.download
            else:
                logging.info("output file already exists; skipping %s" % resource['id'])

        return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message()

        input_image = resource['local_paths'][0]

        # Create output in same directory as input, but check name
        ds_md = get_info(connector, host, secret_key, resource['parent']['id'])
        dataset_name = ds_md['name']
        timestamp = dataset_name.split(" - ")[1]
        # Is this left or right half?
        side = 'left' if resource['name'].find("_left") > -1 else 'right'
        out_csv = self.sensors.create_sensor_path(timestamp, opts=[side], ext='csv')

        logging.info("Rscript gift.R -f %s --table -o %s" % (input_image, out_csv))
        subprocess.call(["Rscript gift.R -f %s --table -o %s" % (input_image, out_csv)], shell=True)

        fileid = None
        if os.path.isfile(out_csv):
            if out_csv not in resource['local_paths']:
                # TODO: Should this be written to a separate dataset?
                #target_dsid = build_dataset_hierarchy(connector, host, secret_key, self.clowderspace,
                #                                      self.sensors.get_display_name(),
                #                                      timestamp[:4], timestamp[5:7], timestamp[8:10], leaf_ds_name=dataset_name)

                # Send output to Clowder source dataset
                fileid = upload_to_dataset(connector, host, secret_key, resource['parent']['id'], out_csv)
            self.created += 1
            self.bytes += os.path.getsize(out_csv)

        # Add metadata to original dataset indicating this was run
        ext_meta = build_metadata(host, self.extractor_info, resource['parent']['id'], {
            "files_created": [fileid]
        }, 'dataset')
        upload_metadata(connector, host, secret_key, resource['parent']['id'], ext_meta)

        self.end_message()

if __name__ == "__main__":
    extractor = gift()
    extractor.start()
