#!/usr/bin/env python

"""
This extractor triggers when a file is added to a dataset in Clowder.

It checks for _left and _right BIN files to convert them into
JPG and TIF formats.
 """

import os
import shutil
import tempfile
import yaml
from pyclowder.utils import CheckMessage
from pyclowder.datasets import download_metadata, upload_metadata, remove_metadata
from terrautils.metadata import get_extractor_metadata, get_terraref_metadata
from terrautils.extractors import TerrarefExtractor, is_latest_file, load_json_file, \
    build_metadata, build_dataset_hierarchy_crawl, upload_to_dataset, file_exists
from terrautils.formats import create_geotiff, create_image
from terrautils.spatial import geojson_to_tuples, geojson_to_tuples_betydb
from terrautils.lemnatec import _get_experiment_metadata
from terrautils.gdal import centroid_from_geojson, clip_raster
from terrautils.betydb import add_arguments, get_site_boundaries
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

        # Check metadata to verify we have what we need
        md = download_metadata(connector, host, secret_key, resource['id'])
        if get_extractor_metadata(md, self.extractor_info['name']) and not self.overwrite:
            self.log_skip(resource, "metadata indicates it was already processed")
            return CheckMessage.ignore
        if get_terraref_metadata(md):
            return CheckMessage.download
        else:
            self.log_skip(resource, "no terraref metadata found")
            return CheckMessage.ignore

        # TODO do we remove this? It was not in the flir2tiff?
        # Check if outputs already exist unless overwrite is forced - skip if found
        if not self.overwrite:
            timestamp = resource['dataset_info']['name'].split(" - ")[1]
            lbase = self.sensors.get_sensor_path(timestamp, opts=['left'], ext='')
            rbase = self.sensors.get_sensor_path(timestamp, opts=['right'], ext='')
            out_dir = os.path.dirname(lbase)
            if (file_exists(lbase+'tif') and file_exists(rbase+'tif')):
                self.log_skip(resource, "outputs found in %s" % out_dir)
                return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message(resource)

        # Get left/right files and metadata
        img_left, img_right, metadata = None, None, None
        for fname in resource['local_paths']:
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = load_json_file(fname)
                terra_md_full = get_terraref_metadata(all_dsmd, 'stereoTop')
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [img_left, img_right, terra_md_full]:
            self.log_error(resource, "could not locate each of left+right+metadata in processing")
            raise ValueError("could not locate each of left+right+metadata in processing")

        # Determine output location & filenames
        timestamp = resource['dataset_info']['name'].split(" - ")[1]

        # Fetch experiment name from terra metadata
        season_name = None
        experiment_name = None
        updated_experiment = False
        if 'experiment_metadata' in terra_md_full and len(terra_md_full['experiment_metadata']) > 0:
            for experiment in terra_md_full['experiment_metadata']:
                if 'name' in experiment:
                    if ":" in experiment['name']:
                        season_name = experiment['name'].split(": ")[0]
                        experiment_name = experiment['name'].split(": ")[1]
                    else:
                        experiment_name = experiment['name']
                        season_name = None
                    break
        else:
            # Try to determine experiment data dynamically
            expmd = _get_experiment_metadata(timestamp.split("__")[0], 'stereoTop')
            if len(expmd) > 0:
                updated_experiment = True
                for experiment in expmd:
                    if 'name' in experiment:
                        if ":" in experiment['name']:
                            season_name = experiment['name'].split(": ")[0]
                            experiment_name = experiment['name'].split(": ")[1]
                        else:
                            experiment_name = experiment['name']
                            season_name = None
                        break
        if season_name is None:
            season_name = 'Unknown Season'
        if experiment_name is None:
            experiment_name = 'Unknown Experiment'

        # TODO below this is old stuff
        left_tiff = self.sensors.create_sensor_path(timestamp, opts=['left'])
        right_tiff = self.sensors.create_sensor_path(timestamp, opts=['right'])

        self.log_info(resource, "Hierarchy: %s / %s / %s / %s / %s / %s / %s" % (
            season_name, experiment_name, self.sensors.get_display_name(), timestamp[:4], timestamp[5:7],
            timestamp[8:10], timestamp
        ))

        target_dsid = build_dataset_hierarchy_crawl(host, secret_key, self.clowder_user, self.clowder_pass, self.clowderspace,
                                              self.sensors.get_display_name(),
                                              timestamp[:4], timestamp[5:7], timestamp[8:10],
                                              leaf_ds_name=self.sensors.get_display_name() + ' - ' + timestamp)

        uploaded_file_ids = []

        self.log_info(resource, "uploading LemnaTec metadata to ds [%s]" % target_dsid)
        remove_metadata(connector, host, secret_key, target_dsid, self.extractor_info['name'])
        terra_md_trim = get_terraref_metadata(all_dsmd)
        if updated_experiment:
            terra_md_trim['experiment_metadata'] = expmd
        terra_md_trim['raw_data_source'] = host + ("" if host.endswith("/") else "/") + "datasets/" + resource['id']
        level1_md = build_metadata(host, self.extractor_info, target_dsid, terra_md_trim, 'dataset')
        upload_metadata(connector, host, secret_key, target_dsid, level1_md)

        left_shape = terraref.stereo_rgb.get_image_shape(metadata, 'left')
        right_shape = terraref.stereo_rgb.get_image_shape(metadata, 'right')
        gps_bounds = geojson_to_tuples(terra_md_full['spatial_metadata']['stereoTop']['bounding_box'])

        if (not file_exists(left_tiff)) or self.overwrite:
            self.log_info(resource, "creating & uploading %s" % left_tiff)
            left_image = terraref.stereo_rgb.process_raw(left_shape, img_left, None)
            out_tmp_tiff_left = os.path.join(tempfile.gettempdir(), resource['id'].encode('utf8'))
             # Rename output.tif after creation to avoid long path errors
            create_geotiff(left_image, gps_bounds, out_tmp_tiff_left, None, True, self.extractor_info, terra_md_full)

            # TODO: we're moving zero byte files
            if os.path.getsize(out_tmp_tiff_left) > 0:
                shutil.move(out_tmp_tiff_left, left_tiff)
                if left_tiff not in resource['local_paths']:
                    fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid,
                                               left_tiff)
                    uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)
                else:
                    self.log_info(resource, "file found in dataset already; not re-uploading")
                self.created += 1
                self.bytes += os.path.getsize(left_tiff)
            else:
                self.log_info("Zero bytes file generated")

        if (not file_exists(right_tiff)) or self.overwrite:
            self.log_info(resource, "creating & uploading %s" % right_tiff)
            right_image = terraref.stereo_rgb.process_raw(left_shape, img_right, None)
            out_tmp_tiff_right = os.path.join(tempfile.gettempdir(), resource['id'].encode('utf8'))
            # Rename output.tif after creation to avoid long path errors
            create_geotiff(right_image, gps_bounds, out_tmp_tiff_right, None, True, self.extractor_info, terra_md_full)
            if os.path.getsize(out_tmp_tiff_right) > 0:
                shutil.move(out_tmp_tiff_right, right_tiff)
                if left_tiff not in resource['local_paths']:
                    fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid,
                                               left_tiff)
                    uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)
                else:
                    self.log_info(resource, "file found in dataset already; not re-uploading")
                self.created += 1
                self.bytes += os.path.getsize(left_tiff)
            else:
                self.log_info("Zero bytes file generated")


        # Plot dir is the day under Level_1_Plots/ir_geotiff/day
        # TODO
        # 1. Should this be done above, each in the block for left, right?
        # 2. Or just check if both left and right tiff not zero byte files here?
        self.log_info(resource, "Attempting to clip into plot shards")
        plot_path = os.path.dirname(os.path.dirname(left_tiff.replace("/Level_1/", "/Level_1_Plots/")))
        shard_name = os.path.basename(left_tiff)

        all_plots = get_site_boundaries(timestamp, city='Maricopa')
        for plotname in all_plots:
            if plotname.find("KSU") > -1:
                continue

            bounds = all_plots[plotname]
            tuples = geojson_to_tuples_betydb(yaml.safe_load(bounds))
            shard_path = os.path.join(plot_path, plotname, shard_name)
            if not os.path.exists(os.path.dirname(shard_path)):
                os.makedirs(os.path.dirname(shard_path))
            clip_raster(left_tiff, tuples, out_path=shard_path)

        self.log_info(resource, "Attempting to clip into plot shards")
        plot_path = os.path.dirname(os.path.dirname(left_tiff.replace("/Level_1/", "/Level_1_Plots/")))
        shard_name = os.path.basename(right_tiff)

        all_plots = get_site_boundaries(timestamp, city='Maricopa')
        for plotname in all_plots:
            if plotname.find("KSU") > -1:
                continue

            bounds = all_plots[plotname]
            tuples = geojson_to_tuples_betydb(yaml.safe_load(bounds))
            shard_path = os.path.join(plot_path, plotname, shard_name)
            if not os.path.exists(os.path.dirname(shard_path)):
                os.makedirs(os.path.dirname(shard_path))
            clip_raster(right_tiff, tuples, out_path=shard_path)


        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        extractor_md = build_metadata(host, self.extractor_info, target_dsid, {
            "files_created": uploaded_file_ids
        }, 'dataset')
        self.log_info(resource, "uploading extractor metadata to raw dataset")
        remove_metadata(connector, host, secret_key, resource['id'], self.extractor_info['name'])
        upload_metadata(connector, host, secret_key, resource['id'], extractor_md)

        self.end_message(resource)

if __name__ == "__main__":
    extractor = StereoBin2JpgTiff()
    extractor.start()
