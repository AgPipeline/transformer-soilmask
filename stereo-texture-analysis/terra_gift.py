#!/usr/bin/env python

"""
This extractor will trigger when an image is uploaded into Clowder.

It will create csv file which contains the feature vectors.
"""

import os
import logging
import subprocess
import numpy
from PIL import Image

from pyclowder.utils import CheckMessage
from pyclowder.datasets import get_info, upload_metadata, download_metadata
from pyclowder.files import upload_to_dataset
from terrautils.extractors import TerrarefExtractor, build_dataset_hierarchy, build_metadata
from terrautils.sensors import Sensors
from terrautils.formats import create_geotiff
from terrautils.metadata import get_terraref_metadata


class gift(TerrarefExtractor):
    def __init__(self):
        super(gift, self).__init__()

        # parse command line and load default logging configuration
        self.setup(sensor='texture_analysis')

    def check_message(self, connector, host, secret_key, resource, parameters):
        ds_md = get_info(connector, host, secret_key, resource['parent']['id'])

        s = Sensors('', 'ua-mac', 'rgb_geotiff')
        if ds_md['name'].find(s.get_display_name()) > -1:
            timestamp = ds_md['name'].split(" - ")[1]
            side = 'left' if resource['name'].find("_left") > -1 else 'right'
            out_csv = self.sensors.get_sensor_path(timestamp, opts=[side], ext='csv')

            if not os.path.exists(out_csv) or self.overwrite:
                return CheckMessage.download
            else:
                logging.info("output file already exists; skipping %s" % resource['id'])

        return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message()

        input_image = resource['local_paths'][0]

        # Create output in same directory as input, but check name
        ds_md = get_info(connector, host, secret_key, resource['parent']['id'])
        terra_md = get_terraref_metadata(download_metadata(connector, host, secret_key,
                                                           resource['parent']['id']), 'stereoTop')
        dataset_name = ds_md['name']
        timestamp = dataset_name.split(" - ")[1]

        # Is this left or right half?
        side = 'left' if resource['name'].find("_left") > -1 else 'right'
        out_csv = self.sensors.create_sensor_path(timestamp, opts=[side], ext='csv')
        out_dgci = out_csv.replace(".csv", "_dgci.png")
        out_edge = out_csv.replace(".csv", "_edge.png")
        out_label = out_csv.replace(".csv", "_label.png")

        # Generate actual output CSV and PNGs
        cmd = "Rscript gift.R -f %s " % input_image
        cmd += "--table -o %s " % out_csv
        cmd += "--dgci --outputdgci %s " % out_dgci
        cmd += "--edge --outputedge %s " % out_edge
        cmd += "--label --outputlabel %s " % out_label
        logging.info(cmd)
        subprocess.call([cmd], shell=True)

        # Convert PNGs to GeoTIFFs
        gps_bounds = terra_md['spatial_metadata'][side]['bounding_box']
        for png_path in [out_dgci, out_edge, out_label]:
            tif_path = png_path.replace(".png", ".tif")
            with Image.open(png_path) as png:
                px_array = numpy.array(png)
                create_geotiff(px_array, gps_bounds, tif_path)

        # Remove PNGs
        out_dgci_tif = out_dgci.replace('.png', '.tif')
        out_edge_tif = out_edge.replace('.png', '.tif')
        out_label_tif = out_label.replace('.png', '.tif')
        os.remove(out_dgci)
        os.remove(out_edge)
        os.remove(out_label)

        fileids = []
        for file_to_upload in [out_csv, out_dgci_tif, out_edge_tif, out_label_tif]:
            if os.path.isfile(file_to_upload):
                if file_to_upload not in resource['local_paths']:
                    # TODO: Should this be written to a separate dataset?
                    #target_dsid = build_dataset_hierarchy(connector, host, secret_key, self.clowderspace,
                    #                                      self.sensors.get_display_name(),
                    #                                      timestamp[:4], timestamp[5:7], timestamp[8:10], leaf_ds_name=dataset_name)

                    # Send output to Clowder source dataset
                    fileids.append(upload_to_dataset(connector, host, secret_key, resource['parent']['id'], file_to_upload))
                self.created += 1
                self.bytes += os.path.getsize(file_to_upload)

        # Add metadata to original dataset indicating this was run
        ext_meta = build_metadata(host, self.extractor_info, resource['parent']['id'], {
            "files_created": fileids
        }, 'dataset')
        upload_metadata(connector, host, secret_key, resource['parent']['id'], ext_meta)

        self.end_message()

if __name__ == "__main__":
    extractor = gift()
    extractor.start()
