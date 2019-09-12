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
from pyclowder.datasets import download_metadata, upload_metadata, remove_metadata, submit_extraction
from terrautils.metadata import get_extractor_metadata, get_terraref_metadata, get_season_and_experiment
from terrautils.extractors import TerrarefExtractor, is_latest_file, check_file_in_dataset, load_json_file, \
    build_metadata, build_dataset_hierarchy_crawl, upload_to_dataset, file_exists, contains_required_files
from terrautils.formats import create_geotiff, create_image
from terrautils.spatial import geojson_to_tuples, geojson_to_tuples_betydb
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
        if not contains_required_files(resource, ['_left.bin', '_right.bin']):
            self.log_skip(resource, "missing required files")
            return CheckMessage.ignore

        # Check metadata to verify we have what we need
        md = download_metadata(connector, host, secret_key, resource['id'])
        if get_terraref_metadata(md):
            if not self.overwrite and get_extractor_metadata(md, self.extractor_info['name'], self.extractor_info['version']):
                # Make sure outputs properly exist
                timestamp = resource['dataset_info']['name'].split(" - ")[1]
                left_tiff = self.sensors.create_sensor_path(timestamp, opts=['left'])
                right_tiff = self.sensors.create_sensor_path(timestamp, opts=['right'])
                if file_exists(left_tiff) and file_exists(right_tiff):
                    self.log_skip(resource, "metadata v%s and outputs already exist" % self.extractor_info['version'])
            # Have TERRA-REF metadata, but not any from this extractor
            return CheckMessage.download
        else:
            self.log_error(resource, "no terraref metadata found; sending to cleaner")
            submit_extraction(connector, host, secret_key, resource['id'], "terra.metadata.cleaner")
            return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message(resource)

        # Get left/right files and metadata
        img_left, img_right, terra_md_full = None, None, None
        for fname in resource['local_paths']:
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = load_json_file(fname)
                terra_md_full = get_terraref_metadata(all_dsmd, 'stereoTop')
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [img_left, img_right, terra_md_full]:
            raise ValueError("could not locate all files & metadata in processing")

        timestamp = resource['dataset_info']['name'].split(" - ")[1]

        # Fetch experiment name from terra metadata
        season_name, experiment_name, updated_experiment = get_season_and_experiment(timestamp, 'stereoTop', terra_md_full)
        if None in [season_name, experiment_name]:
            raise ValueError("season and experiment could not be determined")

        # Determine output directory
        self.log_info(resource, "Hierarchy: %s / %s / %s / %s / %s / %s / %s" % (season_name, experiment_name, self.sensors.get_display_name(),
                                                                                 timestamp[:4], timestamp[5:7], timestamp[8:10], timestamp))
        target_dsid = build_dataset_hierarchy_crawl(host, secret_key, self.clowder_user, self.clowder_pass, self.clowderspace,
                                              season_name, experiment_name, self.sensors.get_display_name(),
                                              timestamp[:4], timestamp[5:7], timestamp[8:10],
                                              leaf_ds_name=self.sensors.get_display_name() + ' - ' + timestamp)
        left_tiff = self.sensors.create_sensor_path(timestamp, opts=['left'])
        right_tiff = self.sensors.create_sensor_path(timestamp, opts=['right'])
        uploaded_file_ids = []

        # Attach LemnaTec source metadata to Level_1 product if necessary
        target_md = download_metadata(connector, host, secret_key, target_dsid)
        if not get_extractor_metadata(target_md, self.extractor_info['name']):
            self.log_info(resource, "uploading LemnaTec metadata to ds [%s]" % target_dsid)
            remove_metadata(connector, host, secret_key, target_dsid, self.extractor_info['name'])
            terra_md_trim = get_terraref_metadata(all_dsmd)
            if updated_experiment is not None:
                terra_md_trim['experiment_metadata'] = updated_experiment
            terra_md_trim['raw_data_source'] = host + ("" if host.endswith("/") else "/") + "datasets/" + resource['id']
            level1_md = build_metadata(host, self.extractor_info, target_dsid, terra_md_trim, 'dataset')
            upload_metadata(connector, host, secret_key, target_dsid, level1_md)

        try:
            left_shape = terraref.stereo_rgb.get_image_shape(terra_md_full, 'left')
            gps_bounds_left = geojson_to_tuples(terra_md_full['spatial_metadata']['left']['bounding_box'])
            right_shape = terraref.stereo_rgb.get_image_shape(terra_md_full, 'right')
            gps_bounds_right = geojson_to_tuples(terra_md_full['spatial_metadata']['right']['bounding_box'])
        except KeyError:
            self.log_error(resource, "spatial metadata not properly identified; sending to cleaner")
            submit_extraction(connector, host, secret_key, resource['id'], "terra.metadata.cleaner")
            return

        if (not file_exists(left_tiff)) or self.overwrite:
            # Perform actual processing
            self.log_info(resource, "creating %s" % left_tiff)
            left_image = terraref.stereo_rgb.process_raw(left_shape, img_left, None)
            create_geotiff(left_image, gps_bounds_left, left_tiff, None, True,
                           self.extractor_info, terra_md_full, compress=True)
            self.created += 1
            self.bytes += os.path.getsize(left_tiff)
        # Check if the file should be uploaded, even if it was already created
        found_in_dest = check_file_in_dataset(connector, host, secret_key, target_dsid, left_tiff)
        if not found_in_dest:
            self.log_info(resource, "uploading %s" % left_tiff)
            fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid, left_tiff)
            uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)


        if (not file_exists(right_tiff)) or self.overwrite:
            # Perform actual processing
            self.log_info(resource, "creating %s" % right_tiff)
            right_image = terraref.stereo_rgb.process_raw(right_shape, img_right, None)
            create_geotiff(right_image, gps_bounds_right, right_tiff, None, True,
                           self.extractor_info, terra_md_full, compress=True)
            self.created += 1
            self.bytes += os.path.getsize(right_tiff)
        # Check if the file should be uploaded, even if it was already created
        found_in_dest = check_file_in_dataset(connector, host, secret_key, target_dsid, right_tiff)
        if not found_in_dest:
            self.log_info(resource, "uploading %s" % right_tiff)
            fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid, right_tiff)
            uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)

        # Trigger additional extractors
        self.log_info(resource, "triggering downstream extractors")
        submit_extraction(connector, host, secret_key, target_dsid, "terra.stereo-rgb.rgbmask")
        submit_extraction(connector, host, secret_key, target_dsid, "terra.stereo-rgb.nrmac")
        submit_extraction(connector, host, secret_key, target_dsid, "terra.plotclipper_tif")

        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        if len(uploaded_file_ids) > 0:
            extractor_md = build_metadata(host, self.extractor_info, target_dsid, {
                "files_created": uploaded_file_ids
            }, 'dataset')
            self.log_info(resource, "uploading extractor metadata to raw dataset")
            remove_metadata(connector, host, secret_key, resource['id'], self.extractor_info['name'])
            try:
                upload_metadata(connector, host, secret_key, resource['id'], extractor_md)
            except:
                self.log_info(resource, "problem uploading extractor metadata...")

        self.end_message(resource)

if __name__ == "__main__":
    extractor = StereoBin2JpgTiff()
    extractor.start()
