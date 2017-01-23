'''
Created on Oct 31, 2016

@author: Zongyang
'''


import os
import json
import logging
import requests

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
import pyclowder.datasets

import canopyCover as ccCore


def determineOutputDirectory(outputRoot, dsname):
    if dsname.find(" - ") > -1:
        timestamp = dsname.split(" - ")[1]
    else:
        timestamp = "dsname"
    if timestamp.find("__") > -1:
        datestamp = timestamp.split("__")[0]
    else:
        datestamp = ""

    return os.path.join(outputRoot, datestamp, timestamp)

class CanopyCoverHeight(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        # add any additional arguments to parser
        # self.parser.add_argument('--max', '-m', type=int, nargs='?', default=-1,
        #                          help='maximum number (default=-1)')
        self.parser.add_argument('--output', '-o', dest="output_dir", type=str, nargs='?',
                                 default="/home/extractor/sites/ua-mac/Level_1/demosaic",
                                 help="root directory where timestamp & output directories will be created")
        self.parser.add_argument('--overwrite', dest="force_overwrite", type=bool, nargs='?', default=False,
                                 help="whether to overwrite output file if it already exists in output directory")
        self.parser.add_argument('--betyURL', dest="bety_url", type=str, nargs='?',
                                 default="https://terraref.ncsa.illinois.edu/bety/api/beta/traits.csv",
                                 help="traits API endpoint of BETY instance that outputs should be posted to")
        self.parser.add_argument('--betyKey', dest="bety_key", type=str, nargs='?', default=False,
                                 help="API key for BETY instance specified by betyURL")

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the exctractor
        logging.getLogger('pyclowder').setLevel(logging.DEBUG)
        logging.getLogger('__main__').setLevel(logging.DEBUG)

        # assign other arguments
        self.output_dir = self.args.output_dir
        self.force_overwrite = self.args.force_overwrite
        self.bety_url = self.args.bety_url
        self.bety_key = self.args.bety_key

    def check_message(self, connector, host, secret_key, resource, parameters):
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
        out_dir = determineOutputDirectory(self.output_dir, resource['dataset_info']['name'])
        if not self.force_overwrite:
            outfile = os.path.join(out_dir, 'CanopyCoverTraits.csv')
            if os.path.isfile(outfile):
                logging.info("skipping dataset %s, output already exists" % resource['id'])
                return CheckMessage.ignore

        # fetch metadata from dataset to check if we should remove existing entry for this extractor first
        md = pyclowder.datasets.download_metadata(connector, host, secret_key,
                                                  resource['id'], self.extractor_info['name'])
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
        metafile, img_left, img_right, metadata = None, None, None, None

        # Get left/right files and metadata
        for fname in resource['local_paths']:
            # First check metadata attached to dataset in Clowder for item of interest
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = load_json(fname)
                for curr_dsmd in all_dsmd:
                    if 'content' in curr_dsmd and 'lemnatec_measurement_metadata' in curr_dsmd['content']:
                        metafile = fname
                        metadata = curr_dsmd['content']
            # Otherwise, check if metadata was uploaded as a .json file
            elif fname.endswith('_metadata.json') and fname.find('/_metadata.json') == -1 and metafile is None:
                metafile = fname
                metadata = load_json(metafile)
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [metafile, img_left, img_right, metadata]:
            logging.error('could not find all 3 of left/right/metadata')
            return

        # Determine output directory
        out_dir = determineOutputDirectory(self.output_dir, resource['dataset_info']['name'])
        logging.info("...writing outputs to: %s" % out_dir)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        outfile = os.path.join(out_dir, 'CanopyCoverTraits.csv')

        # Get information from input data
        metadata = ccCore.lower_keys(metadata)
        plotNum = ccCore.get_plot_num(metadata)
        ccVal = ccCore.get_CC_from_bin(img_left)

        # generate output CSV & send to Clowder + BETY
        (fields, traits) = ccCore.get_traits_table()
        str_time = str(ccCore.get_localdatetime(metadata))
        str_date = str_time[6:10]+'-'+str_time[:5]+'T'+str_time[11:]
        traits['local_datetime'] = str_date.replace("/", '-')
        traits['canopy_cover'] = str(ccVal)
        traits['site'] = 'MAC Field Scanner Field Plot '+ str(plotNum)
        trait_list = ccCore.generate_traits_list(traits)
        ccCore.generate_cc_csv(outfile, fields, trait_list)
        logging.info("...uploading CSV to Clowder")
        pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], outfile)
        self.submitToBety(outfile)

        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        metadata = {
            # TODO: Generate JSON-LD context for additional fields
            "@context": ["https://clowder.ncsa.illinois.edu/contexts/metadata.jsonld"],
            "dataset_id": resource['id'],
            "content": {"status": "COMPLETED"},
            "agent": {
                "@type": "cat:extractor",
                "extractor_id": host + "/api/extractors/" + self.extractor_info['name']
            }
        }
        pyclowder.datasets.upload_metadata(connector, host, secret_key, resource['id'], metadata)

    def submitToBety(self, csvfile):
        if self.bety_url != "":
            sess = requests.Session()

            r = sess.post("%s?key=%s" % (self.bety_url, self.bety_key),
                      data=file(csvfile, 'rb').read(),
                      headers={'Content-type': 'text/csv'})

            if r.status_code == 200 or r.status_code == 201:
                logging.info("...CSV successfully uploaded to BETYdb.")
            else:
                print("Error uploading CSV to BETYdb %s" % r.status_code)
                print(r.text)

def load_json(meta_path):
    try:
        with open(meta_path, 'r') as fin:
            return json.load(fin)
    except Exception as ex:
        logging.error('Corrupt metadata file, ' + str(ex))

if __name__ == "__main__":
    extractor = CanopyCoverHeight()
    extractor.start()
