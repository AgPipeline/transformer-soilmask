#!/usr/bin/env python

"""
This extractor triggers when a file is added to a dataset in Clowder.

It checks for _left and _right BIN files to convert them into
JPG and TIF formats.
 """

import os
import shutil
import tempfile

from pyclowder.utils import CheckMessage
from pyclowder.datasets import download_metadata, upload_metadata, remove_metadata
from terrautils.metadata import get_extractor_metadata, get_terraref_metadata
from terrautils.extractors import TerrarefExtractor, is_latest_file, load_json_file, \
    build_metadata, build_dataset_hierarchy, upload_to_dataset
from terrautils.formats import create_geotiff, create_image
from terrautils.spatial import geojson_to_tuples

import terraref.stereo_rgb


class StereoBin2JpgTiff(TerrarefExtractor):
    def __init__(self):
        super(StereoBin2JpgTiff, self).__init__()

        # parse command line and load default logging configuration
        self.setup(sensor='rgb_geotiff')

    def check_message(self, connector, host, secret_key, resource, parameters):
        if "rulechecked" in parameters and parameters["rulechecked"]:
            return CheckMessage.download
        self.start_check(resource)

        if not is_latest_file(resource):
            self.log_skip(resource, "not latest file")
            return CheckMessage.ignore

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
            self.log_skip(resource, "found left: %s, right: %s" % (found_left, found_right))
            return CheckMessage.ignore

        # Check if outputs already exist unless overwrite is forced - skip if found
        if not self.overwrite:
            timestamp = resource['dataset_info']['name'].split(" - ")[1]
            lbase = self.sensors.get_sensor_path(timestamp, opts=['left'], ext='')
            rbase = self.sensors.get_sensor_path(timestamp, opts=['right'], ext='')
            out_dir = os.path.dirname(lbase)
            if (os.path.isfile(lbase+'tif') and os.path.isfile(rbase+'tif')):
                self.log_skip(resource, "outputs found in %s" % out_dir)
                return CheckMessage.ignore

        # Check metadata to verify we have what we need
        md = download_metadata(connector, host, secret_key, resource['id'])
        if get_extractor_metadata(md, self.extractor_info['name']) and not self.overwrite:
            self.log_skip("metadata indicates it was already processed")
            return CheckMessage.ignore
        if get_terraref_metadata(md):
            return CheckMessage.download
        else:
            self.log_skip("no terraref metadata found")
            return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message(resource)

        # Get left/right files and metadata
        img_left, img_right, metadata = None, None, None
        for fname in resource['local_paths']:
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = load_json_file(fname)
                metadata = get_terraref_metadata(all_dsmd, 'stereoTop')
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [img_left, img_right, metadata]:
            self.log_error(resource, "could not locate each of left+right+metadata in processing")
            raise ValueError("could not locate each of left+right+metadata in processing")

        # Determine output location & filenames
        timestamp = resource['dataset_info']['name'].split(" - ")[1]
        left_tiff = self.sensors.create_sensor_path(timestamp, opts=['left'])
        right_tiff = self.sensors.create_sensor_path(timestamp, opts=['right'])
        uploaded_file_ids = []

        self.log_info(resource, "determining image shapes & gps bounds")
        left_shape = terraref.stereo_rgb.get_image_shape(metadata, 'left')
        right_shape = terraref.stereo_rgb.get_image_shape(metadata, 'right')

        left_gps_bounds = geojson_to_tuples(metadata['spatial_metadata']['left']['bounding_box'])
        right_gps_bounds = geojson_to_tuples(metadata['spatial_metadata']['right']['bounding_box'])
        out_tmp_tiff = os.path.join(tempfile.gettempdir(), resource['id'].encode('utf8'))

        target_dsid = build_dataset_hierarchy(host, secret_key, self.clowder_user, self.clowder_pass, self.clowderspace,
                                              self.sensors.get_display_name(),
                                              timestamp[:4], timestamp[5:7], timestamp[8:10],
                                              leaf_ds_name=self.sensors.get_display_name()+' - '+timestamp)

        # Upload original Lemnatec metadata to new Level_1 dataset
        md = get_terraref_metadata(all_dsmd)
        md['raw_data_source'] = host + ("" if host.endswith("/") else "/") + "datasets/" + resource['id']
        lemna_md = build_metadata(host, self.extractor_info, target_dsid, md, 'dataset')
        self.log_info(resource, "uploading LemnaTec metadata")
        upload_metadata(connector, host, secret_key, target_dsid, lemna_md)


        if (not os.path.isfile(left_tiff)) or self.overwrite:
            self.log_info(resource, "creating & uploading %s" % left_tiff)
            left_image = terraref.stereo_rgb.process_raw(left_shape, img_left, None)

            # Rename output.tif after creation to avoid long path errors
            create_geotiff(left_image, left_gps_bounds, out_tmp_tiff, None, False, self.extractor_info, metadata)
            # TODO: we're moving zero byte files
            shutil.move(out_tmp_tiff, left_tiff)
            if left_tiff not in resource['local_paths']:
                fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid, left_tiff)
                uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)
            else:
                self.log_info(resource, "file found in dataset already; not re-uploading")
            self.created += 1
            self.bytes += os.path.getsize(left_tiff)

        if (not os.path.isfile(right_tiff)) or self.overwrite:
            self.log_info(resource, "creating & uploading %s" % right_tiff)
            right_image = terraref.stereo_rgb.process_raw(right_shape, img_right, None)

            create_geotiff(right_image, right_gps_bounds, out_tmp_tiff, None, False, self.extractor_info, metadata)
            shutil.move(out_tmp_tiff, right_tiff)
            if right_tiff not in resource['local_paths']:
                fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid,right_tiff)
                uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)
            else:
                self.log_info(resource, "file found in dataset already; not re-uploading")
            self.created += 1
            self.bytes += os.path.getsize(right_tiff)

        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        ext_meta = build_metadata(host, self.extractor_info, resource['id'], {
                "files_created": uploaded_file_ids
            }, 'dataset')
        self.log_info(resource, "uploading extractor metadata")
        upload_metadata(connector, host, secret_key, resource['id'], ext_meta)

        self.end_message(resource)

if __name__ == "__main__":
    extractor = StereoBin2JpgTiff()
    extractor.start()
