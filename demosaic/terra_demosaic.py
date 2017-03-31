#!/usr/bin/env python

"""
This extractor triggers when a file is added to a dataset in Clowder.

It checks for _left and _right BIN files to convert them into
JPG and TIF formats.
 """

import os
import logging
import tempfile
import shutil

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
import pyclowder.datasets

import bin_to_geotiff as bin2tiff


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

class StereoBin2JpgTiff(Extractor):
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

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the exctractor
        logging.getLogger('pyclowder').setLevel(logging.DEBUG)
        logging.getLogger('__main__').setLevel(logging.DEBUG)

        # assign other arguments
        self.output_dir = self.args.output_dir
        self.force_overwrite = self.args.force_overwrite

    def check_message(self, connector, host, secret_key, resource, parameters):
        # Check for a left and right file before beginning processing
        found_left = False
        found_right = False
        img_left, img_right = None, None

        for f in resource['files']:
            if 'filename' in f and f['filename'].endswith('_left.bin'):
                found_left = True
                img_left = f['filename']
            elif 'filename' in f and f['filename'].endswith('_right.bin'):
                found_right = True
                img_right = f['filename']
        if not (found_left and found_right):
            return CheckMessage.ignore

        # Check if outputs already exist
        out_dir = determineOutputDirectory(self.output_dir, resource['dataset_info']['name'])
        if not self.force_overwrite:
            lbase = resource['dataset_info']['name']+" (Left)"
            rbase = resource['dataset_info']['name']+" (Right)"
            left_jpg = os.path.join(out_dir, lbase+'.jpg')
            right_jpg = os.path.join(out_dir, rbase+'.jpg')
            left_tiff = os.path.join(out_dir, lbase+'.tif')
            right_tiff = os.path.join(out_dir, rbase+'.tif')

            if (os.path.isfile(left_jpg) and os.path.isfile(right_jpg) and
                    os.path.isfile(left_tiff) and os.path.isfile(right_tiff)):
                logging.info("skipping dataset %s, outputs already exist" % resource['id'])
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
        metafile, img_left, img_right, metadata = None, None, None, None

        # Get left/right files and metadata
        for fname in resource['local_paths']:
            # First check metadata attached to dataset in Clowder for item of interest
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = bin2tiff.load_json(fname)
                for curr_dsmd in all_dsmd:
                    if 'content' in curr_dsmd and 'lemnatec_measurement_metadata' in curr_dsmd['content']:
                        metafile = fname
                        metadata = curr_dsmd['content']
            # Otherwise, check if metadata was uploaded as a .json file
            elif fname.endswith('_metadata.json') and fname.find('/_metadata.json') == -1 and metafile is None:
                metafile = fname
                metadata = bin2tiff.load_json(metafile)
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [metafile, img_left, img_right, metadata]:
            logging.error('could not find all 3 of left/right/metadata')
            return

        out_dir = determineOutputDirectory(self.output_dir, resource['dataset_info']['name'])
        logging.info("...writing outputs to: %s" % out_dir)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        metadata = bin2tiff.lower_keys(metadata)
        # Determine output files
        lbase = resource['dataset_info']['name']+" (Left)"
        rbase = resource['dataset_info']['name']+" (Right)"
        left_jpg = os.path.join(out_dir, lbase+'.jpg')
        right_jpg = os.path.join(out_dir, rbase+'.jpg')
        left_tiff = os.path.join(out_dir, lbase+'.tif')
        right_tiff = os.path.join(out_dir, rbase+'.tif')

        logging.info("...determining image shapes")
        left_shape = bin2tiff.get_image_shape(metadata, 'left')
        right_shape = bin2tiff.get_image_shape(metadata, 'right')

        center_position = bin2tiff.get_position(metadata) # (x, y, z) in meters
        fov = bin2tiff.get_fov(metadata, center_position[2], left_shape) # (fov_x, fov_y) in meters; need to pass in the camera height to get correct fov
        left_position = [center_position[0]+bin2tiff.STEREO_OFFSET, center_position[1], center_position[2]]
        right_position = [center_position[0]-bin2tiff.STEREO_OFFSET, center_position[1], center_position[2]]
        left_gps_bounds = bin2tiff.get_bounding_box_with_formula(left_position, fov) # (lat_max, lat_min, lng_max, lng_min) in decimal degrees
        right_gps_bounds = bin2tiff.get_bounding_box_with_formula(right_position, fov)

        logging.info("...creating JPG images")
        left_image = bin2tiff.process_image(left_shape, img_left, left_jpg)
        right_image = bin2tiff.process_image(right_shape, img_right, right_jpg)
        logging.info("...uploading output JPGs to dataset")
        pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], left_jpg)
        pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'],right_jpg)

        logging.info("...creating geoTIFF images")
        # Rename out.tif after creation to avoid long path errors
        out_tmp_tiff = tempfile.mkstemp()
        bin2tiff.create_geotiff('left', left_image, left_gps_bounds, out_tmp_tiff[1])
        shutil.copyfile(out_tmp_tiff[1], left_tiff)
        os.remove(out_tmp_tiff[1])
        out_tmp_tiff = tempfile.mkstemp()
        bin2tiff.create_geotiff('right', right_image, right_gps_bounds, out_tmp_tiff[1])
        shutil.copyfile(out_tmp_tiff[1], left_tiff)
        shutil.copyfile(out_tmp_tiff[1], right_tiff)
        os.remove(out_tmp_tiff[1])
        logging.info("...uploading output geoTIFFs to dataset")
        pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], left_tiff)
        pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'],right_tiff)

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

if __name__ == "__main__":
    extractor = StereoBin2JpgTiff()
    extractor.start()
