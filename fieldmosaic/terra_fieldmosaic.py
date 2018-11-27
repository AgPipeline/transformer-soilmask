#!/usr/bin/env python

import os
import logging
import subprocess
import json
import requests

from pyclowder.utils import CheckMessage
from pyclowder.files import upload_metadata, download_info, submit_extraction
from terrautils.extractors import TerrarefExtractor, build_metadata, \
    upload_to_dataset, create_empty_collection, create_empty_dataset, file_exists, \
    check_file_in_dataset, build_dataset_hierarchy_crawl
from terrautils.metadata import get_season_and_experiment

import full_day_to_tiles
import shadeRemoval as shade


def add_local_arguments(parser):
    # add any additional arguments to parser
    parser.add_argument('--darker', type=bool, default=os.getenv('MOSAIC_DARKER', False),
                        help="whether to use multipass mosiacking to select darker pixels")
    parser.add_argument('--split', type=int, default=os.getenv('MOSAIC_SPLIT', 2),
                        help="number of splits to use if --darker is True")
    parser.add_argument('--thumb', action='store_true',
                        help="whether to only generate a 2% thumbnail image")

class FullFieldMosaicStitcher(TerrarefExtractor):
    def __init__(self):
        super(FullFieldMosaicStitcher, self).__init__()

        add_local_arguments(self.parser)

        # parse command line and load default logging configuration
        self.setup(sensor='fullfield')

        # assign local arguments
        self.darker = self.args.darker
        self.split = self.args.split
        self.thumb = self.args.thumb

    def check_message(self, connector, host, secret_key, resource, parameters):
        return CheckMessage.bypass

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message(resource)

        # rulechecker provided some key information for us in parameters
        if type(parameters) is str:
            parameters = json.loads(parameters)
        if 'parameters' in parameters:
            parameters = parameters['parameters']
        if type(parameters) is unicode:
            parameters = json.loads(str(parameters))
        dataset_name = parameters["output_dataset"]
        scan_name = parameters["scan_type"] if "scan_type" in parameters else ""

        timestamp = dataset_name.split(" - ")[1]

        # Input path will suggest which sensor we are seeing
        sensor_name, sensor_lookup = None, None
        for f in resource['files']:
            if f['filepath'].find("rgb_geotiff") > -1:
                sensor_name = "stereoTop"
                sensor_lookup = "rgb_fullfield"
            elif f['filepath'].find("ir_geotiff") > -1:
                sensor_name = "flirIrCamera"
                sensor_lookup = "ir_fullfield"
            elif f['filepath'].find("laser3d_heightmap") > -1:
                sensor_name = "scanner3DTop"
                sensor_lookup = "laser3d_fullfield"
            if sensor_lookup is not None:
                break

        # Fetch experiment name from terra metadata
        season_name, experiment_name, updated_experiment = get_season_and_experiment(timestamp, sensor_name, {})
        if None in [season_name, experiment_name]:
            raise ValueError("season and experiment could not be determined")

        out_tif_full = self.sensors.create_sensor_path(timestamp, sensor=sensor_lookup,
                                                       opts=[scan_name]).replace(" ", "_")
        out_tif_thumb = out_tif_full.replace(".tif", "_thumb.tif")
        out_tif_medium = out_tif_full.replace(".tif", "_10pct.tif")
        out_png = out_tif_full.replace(".tif", ".png")
        out_vrt = out_tif_full.replace(".tif", ".vrt")
        out_dir = os.path.dirname(out_vrt)

        found_all = True
        if self.thumb:
            output_files = [out_tif_thumb]
        else:
            output_files = [out_tif_full, out_tif_medium, out_png]
        for output_file in output_files:
            if not file_exists(output_file):
                found_all = False
                break
        if found_all and not self.overwrite:
            self.log_skip(resource, "all outputs already exist")
            return

        if not self.darker or sensor_lookup != 'rgb_fullfield':
            (nu_created, nu_bytes) = self.generateSingleMosaic(connector, host, secret_key,
                                                               out_dir, out_vrt, out_tif_thumb, out_tif_full,
                                                               out_tif_medium, parameters, resource)
        else:
            (nu_created, nu_bytes) = self.generateDarkerMosaic(connector, host, secret_key,
                                                               out_dir, out_vrt, out_tif_thumb, out_tif_full,
                                                               out_tif_medium, parameters, resource)
        self.created += nu_created
        self.bytes += nu_bytes

        if not self.thumb:
            # Create PNG thumbnail
            self.log_info(resource, "Converting 10pct to %s..." % out_png)
            cmd = "gdal_translate -of PNG %s %s" % (out_tif_medium, out_png)
            subprocess.call(cmd, shell=True)
            self.created += 1
            self.bytes += os.path.getsize(out_png)

        self.log_info(resource, "Hierarchy: %s / %s / %s / %s / %s" % (
            season_name, experiment_name, self.sensors.get_display_name(sensor=sensor_lookup), timestamp[:4], timestamp[5:7]))

        # Get dataset ID or create it, creating parent collections as needed
        target_dsid = build_dataset_hierarchy_crawl(host, secret_key, self.clowder_user, self.clowder_pass, self.clowderspace,
                                              season_name, experiment_name, self.sensors.get_display_name(sensor=sensor_lookup),
                                              timestamp[:4], timestamp[5:7], leaf_ds_name=dataset_name)

        # Upload full field image to Clowder
        content = {
            "comment": "This stitched image is computed based on an assumption that the scene is planar. \
                There are likely to be be small offsets near the boundary of two images anytime there are plants \
                at the boundary (because those plants are higher than the ground plane), or where the dirt is \
                slightly higher or lower than average.",
            "file_ids": parameters["file_paths"]
        }

        # If we newly created these files, upload to Clowder
        if self.thumb:
            generated_files = [out_tif_thumb]
        else:
            generated_files = [out_tif_medium, out_tif_full, out_png]
        for checked_file in generated_files:
            found_in_dest = check_file_in_dataset(connector, host, secret_key, target_dsid, checked_file, remove=self.overwrite,
                                                  replacements=[("ir_fullfield", "fullfield"), ("L2", "L1")])
            if not found_in_dest or self.overwrite:
                id = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid, checked_file)
                meta = build_metadata(host, self.extractor_info, id, content, 'file')
                upload_metadata(connector, host, secret_key, id, meta)

                if checked_file == out_tif_full:
                    # Trigger downstream extractions on full resolution
                    if sensor_lookup == 'ir_fullfield':
                        submit_extraction(connector, host, secret_key, id, "terra.multispectral.meantemp")
                    elif sensor_lookup == 'rgb_fullfield':
                        submit_extraction(connector, host, secret_key, id, "terra.stereo-rgb.canopycover")

        if self.thumb:
            # TODO: Add parameters support to pyclowder submit_extraction()
            r = requests.post("%sapi/%s/%s/extractions?key=%s" % (host, 'file', resource['id'], secret_key),
                              headers={"Content-Type":"application/json"},
                              data=json.dumps({"extractor": 'terra.geotiff.fieldmosaic_full',
                                               "parameters": parameters}))
            r.raise_for_status()

        self.end_message(resource)

    def generateSingleMosaic(self, connector, host, secret_key, out_dir,
                             out_vrt, out_tif_thumb, out_tif_full, out_tif_medium, parameters, resource):
        # Create simple mosaic from geotiff list
        created, bytes = 0, 0

        #if (os.path.isfile(out_vrt) and os.path.getsize(out_vrt) == 0) or (not os.path.isfile(out_vrt)) or self.overwrite:
        fileidpath = self.remapMountPath(connector, str(parameters['file_paths']))
        with open(fileidpath) as flist:
            file_path_list = json.load(flist)
        self.log_info(resource, "processing %s TIFs without dark flag" % len(file_path_list))

        # Write input list to tmp file
        tiflist = "tiflist.txt"
        with open(tiflist, "w") as tifftxt:
            for tpath in file_path_list:
                filepath = self.remapMountPath(connector, tpath)
                tifftxt.write("%s\n" % filepath)

        if (self.thumb and ((not file_exists(out_vrt)) or self.overwrite)) or (
                    not self.thumb and (not file_exists(out_vrt))):
            # Create VRT from every GeoTIFF
            self.log_info(resource, "Creating VRT %s..." % out_vrt)
            full_day_to_tiles.createVrtPermanent(out_dir, tiflist, out_vrt)
            os.remove(tiflist)
            created += 1
            bytes += os.path.getsize(out_vrt)

        if (not file_exists(out_tif_thumb)) or self.overwrite:
            self.log_info(resource, "Converting VRT to %s..." % out_tif_thumb)
            cmd = "gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 " + \
                  "-outsize %s%% %s%% %s %s" % (2, 2, out_vrt, out_tif_thumb)
            subprocess.call(cmd, shell=True)
            created += 1
            bytes += os.path.getsize(out_tif_thumb)

        if not self.thumb:
            if (not file_exists(out_tif_medium)) or self.overwrite:
                self.log_info(resource, "Converting VRT to %s..." % out_tif_medium)
                cmd = "gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 " + \
                      "-outsize %s%% %s%% %s %s" % (10, 10, out_vrt, out_tif_medium)
                subprocess.call(cmd, shell=True)
                created += 1
                bytes += os.path.getsize(out_tif_medium)

            if (not file_exists(out_tif_full)) or self.overwrite:
                logging.info("Converting VRT to %s..." % out_tif_full)
                cmd = "gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 " + \
                      "%s %s" % (out_vrt, out_tif_full)
                subprocess.call(cmd, shell=True)
                created += 1
                bytes += os.path.getsize(out_tif_full)

        return (created, bytes)

    def generateDarkerMosaic(self, connector, host, secret_key, out_dir,
                             out_vrt, out_tif_thumb, out_tif_full, out_tif_medium, parameters, resource):
        # Create dark-pixel mosaic from geotiff list using multipass for darker pixel selection
        created, bytes = 0, 0

        if ((os.path.isfile(out_vrt) and os.path.getsize(out_vrt) == 0) or
                (not os.path.isfile(out_vrt)) or self.overwrite):
            fileidpath = self.remapMountPath(connector, str(parameters['file_paths']))
            with open(fileidpath) as flist:
                file_path_list = json.load(flist)
            self.log_info(resource, "processing %s TIFs with dark flag" % len(file_path_list))

            # Write input list to tmp file
            tiflist = "tiflist.txt"
            with open(tiflist, "w") as tifftxt:
                for tpath in file_path_list:
                    filepath = self.remapMountPath(connector, tpath)
                    tifftxt.write("%s\n" % filepath)

            # Create VRT from every GeoTIFF
            self.log_info(resource, "Creating VRT %s..." % out_vrt)
            full_day_to_tiles.createVrtPermanent(out_dir, tiflist, out_vrt)
            created += 1
            bytes += os.path.getsize(out_vrt)

            # Split full tiflist into parts according to split number
            shade.split_tif_list(tiflist, out_dir, self.split)

            # Generate tiles from each split VRT into numbered folders
            shade.create_diff_tiles_set(out_dir, self.split)

            # Choose darkest pixel from each overlapping tile
            unite_tiles_dir = os.path.join(out_dir, 'unite')
            if not os.path.exists(unite_tiles_dir):
                os.mkdir(unite_tiles_dir)
            shade.integrate_tiles(out_dir, unite_tiles_dir, self.split)

            # If any files didn't have overlap, copy individual tile
            shade.copy_missing_tiles(out_dir, unite_tiles_dir, self.split, tiles_folder_name='tiles_left')

            # Create output VRT from overlapped tiles
            shade.create_unite_tiles(unite_tiles_dir, out_vrt)
            created += 1
            bytes += os.path.getsize(out_vrt)

        if (not file_exists(out_tif_thumb)) or self.overwrite:
            self.log_info(resource, "Converting VRT to %s..." % out_tif_thumb)
            subprocess.call("gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 "+
                            "-outsize %s%% %s%% %s %s" % (2, 2, out_vrt, out_tif_thumb), shell=True)
            created += 1
            bytes += os.path.getsize(out_tif_thumb)

        if not self.thumb:
            if (not file_exists(out_tif_medium)) or self.overwrite:
                self.log_info(resource, "Converting VRT to %s..." % out_tif_medium)
                subprocess.call("gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 "+
                                "-outsize %s%% %s%% %s %s" % (10, 10, out_vrt, out_tif_medium), shell=True)
                created += 1
                bytes += os.path.getsize(out_tif_medium)

            if self.full and (not file_exists(out_tif_full) or self.overwrite):
                if (not os.path.isfile(out_tif_full)) or self.overwrite:
                    logging.info("Converting VRT to %s..." % out_tif_full)
                    subprocess.call("gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 "+
                                    "%s %s" % (out_vrt, out_tif_full), shell=True)
                    created += 1
                    bytes += os.path.getsize(out_tif_full)

        return (created, bytes)

    def remapMountPath(self, connector, path):
        if len(connector.mounted_paths) > 0:
            for source_path in connector.mounted_paths:
                if path.startswith(source_path):
                    return path.replace(source_path, connector.mounted_paths[source_path])
            return path
        else:
            return path

if __name__ == "__main__":
    extractor = FullFieldMosaicStitcher()
    extractor.start()
