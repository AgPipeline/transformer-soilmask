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
import gc

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
        # Check for a left and right BIN file - skip if not found
        found_left = False
        found_right = False
        for f in resource['files']:
            if 'filename' in f:
                if f['filename'].endswith('_left.bin'):
                    found_left = True
                elif f['filename'].endswith('_right.bin'):
                    found_right = True
        if not (found_left and found_right):
            return CheckMessage.ignore

        # Check if outputs already exist unless overwrite is forced - skip if found
        out_dir = determineOutputDirectory(self.output_dir, resource['dataset_info']['name'])
        if not self.force_overwrite:
            lbase = os.path.join(out_dir, resource['dataset_info']['name']+" (Left)")
            rbase = os.path.join(out_dir, resource['dataset_info']['name']+" (Right)")
            if (os.path.isfile(lbase+'.jpg') and os.path.isfile(rbase+'.jpg') and
                    os.path.isfile(lbase+'.tif') and os.path.isfile(rbase+'.tif')):
                logging.info("skipping dataset %s; outputs found in %s" % (resource['id'], out_dir))
                return CheckMessage.ignore

        # Check metadata to verify we have what we need
        md = pyclowder.datasets.download_metadata(connector, host, secret_key, resource['id'])
        found_meta = False
        for m in md:
            # If there is metadata from this extractor, assume it was previously processed
            if not self.force_overwrite:
                if 'agent' in m and 'name' in m['agent']:
                    if m['agent']['name'].endswith(self.extractor_info['name']):
                        logging.info("skipping dataset %s; metadata indicates it was already processed" % resource['id'])
                        return CheckMessage.ignore
            if 'content' in m and 'lemnatec_measurement_metadata' in m['content']:
                found_meta = True

        if found_left and found_right and found_meta:
            return CheckMessage.download
        else:
            return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        img_left = None
        img_right = None
        metadata = None

        # Determine output location & filenames
        out_dir = determineOutputDirectory(self.output_dir, resource['dataset_info']['name'])
        logging.info("...output directory: %s" % out_dir)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        lbase = os.path.join(out_dir, resource['dataset_info']['name']+" (Left)")
        rbase = os.path.join(out_dir, resource['dataset_info']['name']+" (Right)")
        left_jpg = lbase+'.jpg'
        right_jpg = rbase+'.jpg'
        left_tiff = lbase+'.tif'
        right_tiff = rbase+'.tif'

        # Get left/right files and metadata
        for fname in resource['local_paths']:
            if fname.endswith('_dataset_metadata.json'):
                md = bin2tiff.load_json(fname)
                for m in md:
                    if 'content' in m and 'lemnatec_measurement_metadata' in m['content']:
                        metadata = bin2tiff.lower_keys(m['content'])
                        break
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [img_left, img_right, metadata]:
            raise ValueError("could not locate each of left+right+metadata in processing")

        uploaded_file_ids = []

        logging.info("...determining image shapes")
        left_shape = bin2tiff.get_image_shape(metadata, 'left')
        right_shape = bin2tiff.get_image_shape(metadata, 'right')
        center_position = bin2tiff.get_position(metadata) # (x, y, z) in meters
        fov = bin2tiff.get_fov(metadata, center_position[2], left_shape) # (fov_x, fov_y) in meters; need to pass in the camera height to get correct fov
        left_position = [center_position[0]+bin2tiff.STEREO_OFFSET, center_position[1], center_position[2]]
        right_position = [center_position[0]-bin2tiff.STEREO_OFFSET, center_position[1], center_position[2]]
        left_gps_bounds = bin2tiff.get_bounding_box_with_formula(left_position, fov) # (lat_max, lat_min, lng_max, lng_min) in decimal degrees
        right_gps_bounds = bin2tiff.get_bounding_box_with_formula(right_position, fov)

        logging.info("...creating & uploading JPG images")
        if (not os.path.isfile(left_jpg)) or self.force_overwrite:
            left_image = bin2tiff.process_image(left_shape, img_left, left_jpg)
            # Only upload the newly generated file to Clowder if it isn't already in dataset
            if left_jpg not in resource['local_paths']:
                fileid = pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], left_jpg)
                uploaded_file_ids.append(fileid)

        if (not os.path.isfile(right_jpg)) or self.force_overwrite:
            right_image = bin2tiff.process_image(right_shape, img_right, right_jpg)
            if right_jpg not in resource['local_paths']:
                fileid = pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], right_jpg)
                uploaded_file_ids.append(fileid)

        logging.info("...creating & uploading geoTIFF images")
        if (not os.path.isfile(left_tiff)) or self.force_overwrite:
            # Rename out.tif after creation to avoid long path errors
            out_tmp_tiff = tempfile.mkstemp()
            bin2tiff.create_geotiff('left', left_image, left_gps_bounds, out_tmp_tiff[1])
            shutil.copyfile(out_tmp_tiff[1], left_tiff)
            os.remove(out_tmp_tiff[1])
            if left_tiff not in resource['local_paths']:
                fileid = pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], left_tiff)
                uploaded_file_ids.append(fileid)

        if (not os.path.isfile(right_tiff)) or self.force_overwrite:
            out_tmp_tiff = tempfile.mkstemp()
            bin2tiff.create_geotiff('right', right_image, right_gps_bounds, out_tmp_tiff[1])
            shutil.copyfile(out_tmp_tiff[1], right_tiff)
            os.remove(out_tmp_tiff[1])
            if right_tiff not in resource['local_paths']:
                fileid = pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'],right_tiff)
                uploaded_file_ids.append(fileid)

        # Remove existing metadata from this extractor before rewriting
        md = pyclowder.datasets.download_metadata(connector, host, secret_key, resource['id'], self.extractor_info['name'])
        for m in md:
            if 'agent' in m and 'name' in m['agent']:
                if m['agent']['name'].endswith(self.extractor_info['name']):
                    if 'files_created' in m['content']:
                        uploaded_file_ids += m['content']['files_created']
                    pyclowder.datasets.remove_metadata(connector, host, secret_key, resource['id'], self.extractor_info['name'])

        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        metadata = {
            # TODO: Generate JSON-LD context for additional fields
            "@context": ["https://clowder.ncsa.illinois.edu/contexts/metadata.jsonld"],
            "dataset_id": resource['id'],
            "content": {
                "files_created": uploaded_file_ids
            },
            "agent": {
                "@type": "cat:extractor",
                "extractor_id": host + "/api/extractors/" + self.extractor_info['name']
            }
        }
        pyclowder.datasets.upload_metadata(connector, host, secret_key, resource['id'], metadata)

        # GDAL is leaky so try to force garbage collection, otherwise extractor eventually runs out of memory
        gc.collect()

if __name__ == "__main__":
    extractor = StereoBin2JpgTiff()
    extractor.start()
