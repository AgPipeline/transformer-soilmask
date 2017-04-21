'''
Created on Aug 5, 2016

@author: Zongyang Li
'''
import os
import logging
import full_day_to_tiles

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
import pyclowder.datasets


class FullFieldMosaicStitcher(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        # add any additional arguments to parser
        self.parser.add_argument('--output', '-o', dest="output_dir", type=str, nargs='?',
                                 default="/home/extractor/sites/ua-mac/Level_1/fullFieldMosaics",
                                 help="root directory where timestamp & output directories will be created")
        self.parser.add_argument('--overwrite', dest="force_overwrite", type=bool, nargs='?', default=False,
                                 help="whether to overwrite output file if it already exists in output directory")
        self.parser.add_argument('--influxHost', dest="influx_host", type=str, nargs='?',
                                 default="terra-logging.ncsa.illinois.edu", help="InfluxDB URL for logging")
        self.parser.add_argument('--influxPort', dest="influx_port", type=int, nargs='?',
                                 default=8086, help="InfluxDB port")
        self.parser.add_argument('--influxUser', dest="influx_user", type=str, nargs='?',
                                 default="terra", help="InfluxDB username")
        self.parser.add_argument('--influxPass', dest="influx_pass", type=str, nargs='?',
                                 default="", help="InfluxDB password")
        self.parser.add_argument('--influxDB', dest="influx_db", type=str, nargs='?',
                                 default="extractor_db", help="InfluxDB databast")

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the exctractor
        logging.getLogger('pyclowder').setLevel(logging.DEBUG)
        logging.getLogger('__main__').setLevel(logging.DEBUG)

        # assign other arguments
        self.output_dir = self.args.output_dir
        self.force_overwrite = self.args.force_overwrite
        self.influx_host = self.args.influx_host
        self.influx_port = self.args.influx_port
        self.influx_user = self.args.influx_user
        self.influx_pass = self.args.influx_pass
        self.influx_db = self.args.influx_db

    def check_message(self, connector, host, secret_key, resource, parameters):
        return CheckMessage.bypass

    def process_message(self, connector, host, secret_key, resource, parameters):
        out_dir = os.path.join(self.output_dir, parameters["output_dataset"].split(" - ")[1])
        out_file = "stereoTop_fullField.vrt"
        # Write input list to tmp file
        with open("tiflist.txt", "w") as tifftxt:
            for t in parameters["file_list"]:
                tifftxt.write("%s/n" % t)

        # Create VRT from every GeoTIFF
        print("Creating %s..." % out_file)
        full_day_to_tiles.createVrtPermanent(out_dir, "tiflist.txt", out_file)

        # Upload full field image to Clowder
        fileid = pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], out_file)
        print("Uploaded VRT to Clowder [%s]" % fileid)

        # Cleanup
        os.remove("tiflist.txt")


if __name__ == "__main__":
    extractor = FullFieldMosaicStitcher()
    extractor.start()
