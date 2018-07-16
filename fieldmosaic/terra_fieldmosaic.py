#!/usr/bin/env python

import os
import logging
import subprocess
import json
from matplotlib import pyplot as plt
from PIL import Image
from numpy import array

from pyclowder.utils import CheckMessage
from pyclowder.files import upload_metadata, download_info, submit_extraction
from terrautils.extractors import TerrarefExtractor, build_metadata, build_dataset_hierarchy, \
    upload_to_dataset, create_empty_collection, create_empty_dataset
from terrautils.formats import create_image

import full_day_to_tiles
import shadeRemoval as shade


def add_local_arguments(parser):
    # add any additional arguments to parser
    parser.add_argument('--darker', type=bool, default=os.getenv('MOSAIC_DARKER', False),
                        help="whether to use multipass mosiacking to select darker pixels")
    parser.add_argument('--split', type=int, default=os.getenv('MOSAIC_SPLIT', 2),
                        help="number of splits to use if --darker is True")

class FullFieldMosaicStitcher(TerrarefExtractor):
    def __init__(self):
        super(FullFieldMosaicStitcher, self).__init__()

        add_local_arguments(self.parser)

        # parse command line and load default logging configuration
        self.setup(sensor='fullfield')

        # assign local arguments
        self.darker = self.args.darker
        self.split = self.args.split

    def check_message(self, connector, host, secret_key, resource, parameters):
        return CheckMessage.bypass

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message(resource)

        if type(parameters) is str:
            parameters = json.loads(parameters)
        if 'parameters' in parameters:
            parameters = parameters['parameters']
        if type(parameters) is unicode:
            parameters = json.loads(str(parameters))

        # Input path will suggest which sensor we are seeing
        sensor_type = None
        for f in resource['files']:
            filepath = f['filepath']
            for sens in ["rgb_geotiff", "ir_geotiff", "laser3d_heightmap"]:
                if filepath.find(sens) > -1:
                    sensor_type = sens.split("_")[0]
                    break
            if sensor_type is not None:
                break

        # dataset_name = "Full Field - 2017-01-01"
        dataset_name = parameters["output_dataset"]
        scan_name = parameters["scan_type"] if "scan_type" in parameters else ""
        timestamp = dataset_name.split(" - ")[1]

        out_tif_full = self.sensors.create_sensor_path(timestamp, opts=[sensor_type, scan_name])
        out_tif_thumb = out_tif_full.replace(".tif", "_thumb.tif")
        out_tif_medium = out_tif_full.replace(".tif", "_10pct.tif")
        out_png = out_tif_full.replace(".tif", ".png")
        out_vrt = out_tif_full.replace(".tif", ".vrt")
        out_dir = os.path.dirname(out_vrt)

        thumb_exists, med_exists, full_exists = False, False, False

        if os.path.exists(out_tif_thumb):
            thumb_exists = True
        if os.path.exists(out_tif_medium):
            med_exists = True
        if os.path.exists(out_tif_full):
            full_exists = True
        if thumb_exists and med_exists and full_exists and not self.overwrite:
            self.log_skip(resource, "all outputs already exist")
            return

        if not self.darker or sensor_type != 'rgb':
            (nu_created, nu_bytes) = self.generateSingleMosaic(connector, host, secret_key, sensor_type,
                                                               out_dir, out_vrt, out_tif_thumb, out_tif_full,
                                                               out_tif_medium, parameters, resource)
        else:
            (nu_created, nu_bytes) = self.generateDarkerMosaic(connector, host, secret_key, sensor_type,
                                                               out_dir, out_vrt, out_tif_thumb, out_tif_full,
                                                               out_tif_medium, parameters, resource)
        self.created += nu_created
        self.bytes += nu_bytes

        # Get dataset ID or create it, creating parent collections as needed
        target_dsid = build_dataset_hierarchy(host, secret_key, self.clowder_user, self.clowder_pass, self.clowderspace,
                                              self.sensors.get_display_name(), timestamp[:4],
                                              timestamp[5:7], leaf_ds_name=dataset_name)

        # Upload full field image to Clowder
        content = {
            "comment": "This stitched image is computed based on an assumption that the scene is planar. \
                There are likely to be be small offsets near the boundary of two images anytime there are plants \
                at the boundary (because those plants are higher than the ground plane), or where the dirt is \
                slightly higher or lower than average.",
            "file_ids": parameters["file_paths"]
        }

        # If we newly created these files, upload to Clowder
        if os.path.exists(out_tif_thumb) and not thumb_exists:
            id = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid, out_tif_thumb)
            meta = build_metadata(host, self.extractor_info, id, content, 'file')
            upload_metadata(connector, host, secret_key, id, meta)

        if os.path.exists(out_tif_medium) and not med_exists:
            id = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid, out_tif_medium)
            meta = build_metadata(host, self.extractor_info, id, content, 'file')
            upload_metadata(connector, host, secret_key, id, meta)

            # Create PNG thumbnail
            self.log_info(resource, "Converting 10pct to %s..." % out_png)
            px_img = Image.open(out_tif_medium)
            if sensor_type == 'ir':
                # Get some additional info so we can scale and assign colormap
                ncols, nrows = px_img.size
                px_array = array(px_img.getdata()).reshape((nrows, ncols))
                create_image(px_array, out_png, True)
            elif sensor_type == 'rgb':
                px_img.save(out_png)

        if os.path.exists(out_tif_full) and not full_exists:
            id = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid, out_tif_full)
            meta = build_metadata(host, self.extractor_info, id, content, 'file')
            upload_metadata(connector, host, secret_key, id, meta)

            # Trigger downstream extractions on full resolution
            if sensor_type == 'ir':
                submit_extraction(connector, host, secret_key, id, "terra.multispectral.meantemp")
            elif sensor_type == 'rgb':
                submit_extraction(connector, host, secret_key, id, "terra.stereo-rgb.canopycover")

        self.end_message(resource)

    def generateSingleMosaic(self, connector, host, secret_key, sensor_type, out_dir,
                             out_vrt, out_tif_thumb, out_tif_full, out_tif_medium, parameters, resource):
        # Create simple mosaic from geotiff list
        created, bytes = 0, 0

        if ((os.path.isfile(out_vrt) and os.path.getsize(out_vrt) == 0) or
                (not os.path.isfile(out_vrt)) or self.overwrite):
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

            # Create VRT from every GeoTIFF
            self.log_info(resource, "Creating VRT %s..." % out_vrt)
            full_day_to_tiles.createVrtPermanent(out_dir, tiflist, out_vrt)
            os.remove(tiflist)
            created += 1
            bytes += os.path.getsize(out_vrt)

        if (not os.path.isfile(out_tif_thumb)) or self.overwrite:
            self.log_info(resource, "Converting VRT to %s..." % out_tif_thumb)
            cmd = "gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 " + \
                  "-outsize %s%% %s%% %s %s" % (2, 2, out_vrt, out_tif_thumb)
            subprocess.call(cmd, shell=True)
            created += 1
            bytes += os.path.getsize(out_tif_thumb)

        if (not os.path.isfile(out_tif_medium)) or self.overwrite:
            self.log_info(resource, "Converting VRT to %s..." % out_tif_medium)
            cmd = "gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 " + \
                  "-outsize %s%% %s%% %s %s" % (10, 10, out_vrt, out_tif_medium)
            subprocess.call(cmd, shell=True)
            created += 1
            bytes += os.path.getsize(out_tif_medium)

        if (not os.path.isfile(out_tif_full)) or self.overwrite:
            logging.info("Converting VRT to %s..." % out_tif_full)
            cmd = "gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 " + \
                  "%s %s" % (out_vrt, out_tif_full)
            subprocess.call(cmd, shell=True)
            created += 1
            bytes += os.path.getsize(out_tif_full)

        return (created, bytes)

    def generateDarkerMosaic(self, connector, host, secret_key, sensor_type, out_dir,
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

        if (not os.path.isfile(out_tif_thumb)) or self.overwrite:
            self.log_info(resource, "Converting VRT to %s..." % out_tif_thumb)
            subprocess.call("gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 "+
                            "-outsize %s%% %s%% %s %s" % (2, 2, out_vrt, out_tif_thumb), shell=True)
            created += 1
            bytes += os.path.getsize(out_tif_thumb)

        if (not os.path.isfile(out_tif_medium)) or self.overwrite:
            self.log_info(resource, "Converting VRT to %s..." % out_tif_medium)
            subprocess.call("gdal_translate -projwin -111.9750963 33.0764953 -111.9747967 33.074485715 "+
                            "-outsize %s%% %s%% %s %s" % (10, 10, out_vrt, out_tif_medium), shell=True)
            created += 1
            bytes += os.path.getsize(out_tif_medium)

        if self.full and (not os.path.isfile(out_tif_full) or self.overwrite):
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
