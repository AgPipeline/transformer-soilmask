#!/usr/bin/env python

"""
This extractor will trigger when an image is uploaded into Clowder.

It will create csv file which contains the feature vectors.
"""

import os
import logging
import subprocess
import datetime

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
import pyclowder.datasets
import terrautils.extractors


class gift(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        influx_host = os.getenv("INFLUXDB_HOST", "terra-logging.ncsa.illinois.edu")
        influx_port = os.getenv("INFLUXDB_PORT", 8086)
        influx_db = os.getenv("INFLUXDB_DB", "extractor_db")
        influx_user = os.getenv("INFLUXDB_USER", "terra")
        influx_pass = os.getenv("INFLUXDB_PASSWORD", "")

        # add any additional arguments to parser
        self.parser.add_argument('--output', '-o', dest="output_dir", type=str, nargs='?',
                                 default="/home/extractor/sites/ua-mac/Level_1/texture_analysis",
                                 help="root directory where timestamp & output directories will be created")
        self.parser.add_argument('--overwrite', dest="force_overwrite", type=bool, nargs='?', default=False,
                                 help="whether to overwrite output file if it already exists in output directory")
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
        self.influx_params = {
            "host": self.args.influx_host,
            "port": self.args.influx_port,
            "db": self.args.influx_db,
            "user": self.args.influx_user,
            "pass": self.args.influx_pass
        }

    def check_message(self, connector, host, secret_key, resource, parameters):
        ds_md = pyclowder.datasets.get_info(connector, host, secret_key, resource['parent']['id'])

        if ds_md['name'].find("stereoTop") > -1:
            out_dir = terrautils.extractors.get_output_directory(self.output_dir, ds_md['name'], True)
            out_fname = terrautils.extractors.get_output_filename(ds_md['name'], '.csv', opts=['texture'])
            out_csv =  os.path.join(out_dir, out_fname)
            if not os.path.exists(out_csv) or self.force_overwrite:
                return CheckMessage.download
            else:
                logging.info("output file already exists; skipping %s" % resource['id'])

        return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        starttime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        created = 0
        bytes = 0

        input_image = resource['local_paths'][0]

        # Create output in same directory as input, but check name
        ds_md = pyclowder.datasets.get_info(connector, host, secret_key, resource['parent']['id'])
        out_dir = terrautils.extractors.get_output_directory(self.output_dir, ds_md['name'], True)
        out_fname = terrautils.extractors.get_output_filename(ds_md['name'], '.csv', opts=['texture'])
        out_csv =  os.path.join(out_dir, out_fname)

        subprocess.call(["Rscript", "gift.R",  "-f", input_image, "-t", "-o", out_csv])

        if os.path.isfile(out_csv):
            if out_csv not in resource['local_paths']:
                # Send bmp output to Clowder source dataset
                pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['parent']['id'], out_csv)
            created += 1
            bytes += os.path.getsize(out_csv)

        endtime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        terrautils.extractors.log_to_influxdb(self.extractor_info['name'], self.influx_params,
                                              starttime, endtime, created, bytes)

if __name__ == "__main__":
    extractor = gift()
    extractor.start()
