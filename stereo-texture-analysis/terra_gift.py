#!/usr/bin/env python

"""
This extractor will trigger when an image is uploaded into Clowder.

It will create csv file which contains the feature vectors.
"""

import os
import logging
import subprocess

from pyclowder.utils import CheckMessage
from pyclowder.datasets import get_info
from pyclowder.files import upload_to_dataset


class gift(Extractor):
    def __init__(self):
        super(gift, self).__init__()

        # parse command line and load default logging configuration
        self.setup(sensor='texture_analysis')

    def check_message(self, connector, host, secret_key, resource, parameters):
        ds_md = get_info(connector, host, secret_key, resource['parent']['id'])

        if ds_md['name'].find("stereoTop") > -1:
            timestamp = ds_md['name'].split(" - ")[1]
            out_csv = self.sensors.get_sensor_path(timestamp, opts=['texture'], ext='csv')

            if not os.path.exists(out_csv) or self.force_overwrite:
                return CheckMessage.download
            else:
                logging.info("output file already exists; skipping %s" % resource['id'])

        return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message()

        input_image = resource['local_paths'][0]

        # Create output in same directory as input, but check name
        ds_md = get_info(connector, host, secret_key, resource['parent']['id'])
        timestamp = ds_md['name'].split(" - ")[1]
        out_csv = self.sensors.get_sensor_path(timestamp, opts=['texture'], ext='csv')
        self.sensors.create_sensor_path(out_csv)

        logging.info("Rscript gift.R -f %s --table -o %s" % (input_image, out_csv))
        subprocess.call(["Rscript gift.R -f %s --table -o %s" % (input_image, out_csv)], shell=True)

        if os.path.isfile(out_csv):
            if out_csv not in resource['local_paths']:
                # Send bmp output to Clowder source dataset
                upload_to_dataset(connector, host, secret_key, resource['parent']['id'], out_csv)
            self.created += 1
            self.bytes += os.path.getsize(out_csv)

        self.end_message()

if __name__ == "__main__":
    extractor = gift()
    extractor.start()
