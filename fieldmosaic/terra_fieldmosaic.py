'''
Created on Aug 5, 2016

@author: Zongyang Li
'''
import os
import logging
import requests
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
        self.parser.add_argument('--mainspace', dest="mainspace", type=str, nargs='?',
                                 default="58da6b924f0c430e2baa823f", help="Space UUID in Clowder to store results")
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
        self.mainspace = self.args.mainspace
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
        logging.info("Creating %s..." % out_file)
        full_day_to_tiles.createVrtPermanent(out_dir, "tiflist.txt", out_file)

        # Upload full field image to Clowder
        # parameters["output_dataset"] = "Full Field - 2017-01-01"
        parent_collect = self.getCollectionOrCreate(connector, host, secret_key, "Full Field Stitched Mosaics",
                                                    parent_space=self.mainspace)
        year_collect = self.getCollectionOrCreate(connector, host, secret_key, parameters["output_dataset"][:17],
                                                  parent_collect, self.mainspace)
        month_collect = self.getCollectionOrCreate(connector, host, secret_key, parameters["output_dataset"][:20],
                                                   year_collect, self.mainspace)
        target_dsid = self.getDatasetOrCreate(connector, host, secret_key, parameters["output_dataset"],
                                              month_collect, self.mainspace)

        fileid = pyclowder.files.upload_to_dataset(connector, host, secret_key, target_dsid, out_file)
        pyclowder.files.upload_metadata(connector, host, secret_key, fileid, {
            "@context": ["https://clowder.ncsa.illinois.edu/contexts/metadata.jsonld"],
            "file_id": fileid,
            "content": {
                "comment": "This stitched image is computed based on an assumption that the scene is planar. \
                There are likely to be be small offsets near the boundary of two images anytime there are plants \
                at the boundary (because those plants are higher than the ground plane), or where the dirt is \
                slightly higher or lower than average.",
                "file_source_ids": parameters["file_list"]
            },
            "agent": {
                "@type": "cat:extractor",
                "extractor_id": host + "/api/extractors/" + self.extractor_info['name']
            }
        })
        logging.info("Uploaded VRT to Clowder [%s]" % fileid)

        # Cleanup
        os.remove("tiflist.txt")

    # Fetch dataset from Clowder by name, or create it if not found
    def getCollectionOrCreate(self, connector, host, secret_key, cname, parent_colln=None, parent_space=None):
        url = "%sapi/collections?key=%s&title=" % (host, secret_key, cname)
        result = requests.get(url, verify=connector.ssl_verify)
        result.raise_for_status()

        if len(result.json()) == 0:
            return pyclowder.collections.create_empty(connector, host, secret_key, cname, "",
                                                      parent_colln, parent_space)
        else:
            return result.json()[0]['id']

    # Fetch dataset from Clowder by name, or create it if not found
    def getDatasetOrCreate(self, connector, host, secret_key, dsname, parent_colln=None, parent_space=None):
        url = "%sapi/datasets?key=%s&title=" % (host, secret_key, dsname)
        result = requests.get(url, verify=connector.ssl_verify)
        result.raise_for_status()

        if len(result.json()) == 0:
            return pyclowder.datasets.create_empty(connector, host, secret_key, dsname, "",
                                                   parent_colln, parent_space)
        else:
            return result.json()[0]['id']

if __name__ == "__main__":
    extractor = FullFieldMosaicStitcher()
    extractor.start()
