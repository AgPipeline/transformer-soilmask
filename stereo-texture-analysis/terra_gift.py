#!/usr/bin/env python

"""
This extractor will trigger when an image is uploaded into Clowder.

It will create csv file which contains the feature vectors.
"""

import os
import logging
import subprocess
import numpy
import json
from PIL import Image

from pyclowder.utils import CheckMessage
from pyclowder.datasets import get_info, upload_metadata, download_metadata
from pyclowder.files import upload_to_dataset
from terrautils.extractors import TerrarefExtractor, build_dataset_hierarchy, build_metadata
from terrautils.sensors import Sensors
from terrautils.formats import create_geotiff, create_image
from terrautils.metadata import get_terraref_metadata
from terrautils.betydb import add_arguments, get_site_boundaries, get_sites, get_sites_by_latlon, \
    submit_traits
from terrautils.gdal import clip_raster, centroid_from_geojson
from terrautils.geostreams import create_datapoint_with_dependencies
from terrautils.spatial import geojson_to_tuples


def add_local_arguments(parser):
    # add any additional arguments to parser
    add_arguments(parser)

class gift(TerrarefExtractor):
    def __init__(self):
        super(gift, self).__init__()

        add_local_arguments(self.parser)

        # parse command line and load default logging configuration
        self.setup(sensor='texture_analysis')

        # assign other argumentse
        self.bety_url = self.args.bety_url
        self.bety_key = self.args.bety_key

    def check_message(self, connector, host, secret_key, resource, parameters):
        if resource['name'].find('fullfield') > -1 and resource['name'].find('thumb.tif') == -1:
            return CheckMessage.download

        return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message()

        # Get full list of experiment plots using date as filter
        ds_info = get_info(connector, host, secret_key, resource['parent']['id'])
        timestamp = ds_info['name'].split(" - ")[1]
        all_plots = get_site_boundaries(timestamp, city='Maricopa')

        successful_plots = 0
        for plotname in all_plots:
            bounds = all_plots[plotname]

            # Use GeoJSON string to clip full field to this plot
            try:
                (pxarray, geotrans) = clip_raster(resource['local_paths'][0], bounds)
                if len(pxarray.shape) < 3:
                    logging.error("unexpected array shape for %s (%s)" % (plotname, pxarray.shape))
                    continue

                plot_img = create_image(pxarray, "plot_image.png")
                plot_csv = "plot.csv"
                self.generate_table_only(plot_img, plot_csv)
                trait_vals = self.extract_vals_from_csv(plot_csv)

                successful_plots += 1
                if successful_plots % 10 == 0:
                    logging.info("processed %s/%s plots successfully" % (successful_plots, len(all_plots)))
            except:
                logging.error("error generating traits for %s" % plotname)
                continue

            # Create BETY-ready CSV
            (fields, traits) = self.get_traits_table()
            for tr in trait_vals:
                traits[tr] = str(trait_vals[tr])
            traits['site'] = plotname
            traits['local_datetime'] = timestamp+"T12-00-00-000"
            trait_list = self.generate_traits_list(traits)
            self.generate_cc_csv(plot_csv, fields, trait_list)

            # submit CSV to BETY
            submit_traits(plot_csv, self.bety_key)

            # Prepare and submit datapoint
            centroid_lonlat = json.loads(centroid_from_geojson(bounds))["coordinates"]
            time_fmt = timestamp+"T12:00:00-07:00"
            dpmetadata = {
                "source": host+"files/"+resource['id'],
            }
            for tr in trait_vals:
                dpmetadata[tr] = str(trait_vals[tr])
            create_datapoint_with_dependencies(connector, host, secret_key, "Canopy Cover",
                                               (centroid_lonlat[1], centroid_lonlat[0]), time_fmt, time_fmt,
                                               dpmetadata, timestamp)

            os.remove(plot_img)
            os.remove(plot_csv)

        # Add metadata to original dataset indicating this was run
        ext_meta = build_metadata(host, self.extractor_info, resource['parent']['id'], {
            "plots_processed": successful_plots,
            "plots_skipped": len(all_plots)-successful_plots
            # TODO: add link to BETY trait IDs
        }, 'dataset')
        upload_metadata(connector, host, secret_key, resource['parent']['id'], ext_meta)

        self.end_message()

    def generate_all_outputs(self, input_image, out_csv, out_dgci, out_edge, out_label, gps_bounds):
        # Generate actual output CSV and PNGs
        cmd = "Rscript gift.R -f %s " % input_image
        cmd += "--table -o %s " % out_csv
        cmd += "--dgci --outputdgci %s " % out_dgci
        cmd += "--edge --outputedge %s " % out_edge
        cmd += "--label --outputlabel %s " % out_label
        logging.info(cmd)
        subprocess.call([cmd], shell=True)

        # Convert PNGs to GeoTIFFs
        for png_path in [out_dgci, out_edge, out_label]:
            tif_path = png_path.replace(".png", ".tif")
            with Image.open(png_path) as png:
                px_array = numpy.array(png)
                create_geotiff(px_array, gps_bounds, tif_path)

        # Remove PNGs
        os.remove(out_dgci)
        os.remove(out_edge)
        os.remove(out_label)

    def generate_table_only(self, input_image, out_csv):
        # Generate actual output CSV and PNGs
        cmd = "Rscript gift.R -f %s " % input_image
        cmd += "--table -o %s " % out_csv
        logging.info(cmd)
        subprocess.call([cmd], shell=True)

    def get_traits_table(self):
        # Compiled traits table
        fields = ('local_datetime', 'canopy_cover', 'access_level', 'species', 'site',
                  'citation_author', 'citation_year', 'citation_title', 'method')
        traits = {'local_datetime' : '',
                  'TRAIT_NAME' : [],
                  'access_level': '2',
                  'species': 'Sorghum bicolor',
                  'site': [],
                  'citation_author': '"Hajmohammadi, Solmaz"',
                  'citation_year': '2017',
                  'citation_title': 'Maricopa Field Station Data and Metadata',
                  'method': 'Feature Analysis Vectors'}

        return (fields, traits)

    def generate_traits_list(self, traits):
        # compose the summary traits
        trait_list = [  traits['local_datetime'],
                        traits['TRAIT_NAME'],
                        traits['access_level'],
                        traits['species'],
                        traits['site'],
                        traits['citation_author'],
                        traits['citation_year'],
                        traits['citation_title'],
                        traits['method']
                        ]

        return trait_list

    def generate_cc_csv(self, fname, fields, trait_list):
        """ Generate CSV called fname with fields and trait_list """
        csv = open(fname, 'w')
        csv.write(','.join(map(str, fields)) + '\n')
        csv.write(','.join(map(str, trait_list)) + '\n')
        csv.close()

        return fname

    def extract_vals_from_csv(self, in_csv):
        # TODO: Need to flesh this out
        return {"TRAIT_NAME": 0}


    def check_message_individual(self, connector, host, secret_key, resource, parameters):
        """This is deprecated method that operates on single capture, not field mosaic"""
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

    def process_message_individual(self, connector, host, secret_key, resource, parameters):
        """This is deprecated method that operates on single capture, not field mosaic"""
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
        gps_bounds = geojson_to_tuples(terra_md['spatial_metadata'][side]['bounding_box'])
        out_csv = self.sensors.create_sensor_path(timestamp, opts=[side], ext='csv')
        out_dgci = out_csv.replace(".csv", "_dgci.png")
        out_edge = out_csv.replace(".csv", "_edge.png")
        out_label = out_csv.replace(".csv", "_label.png")
        out_dgci_tif = out_dgci.replace('.png', '.tif')
        out_edge_tif = out_edge.replace('.png', '.tif')
        out_label_tif = out_label.replace('.png', '.tif')

        self.generate_all_outputs(input_image, out_csv, out_dgci, out_edge, out_label,
                                  gps_bounds)

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
