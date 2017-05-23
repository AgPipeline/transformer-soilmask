#!/usr/bin/env python

import os
import json
import logging
import requests
import utm
import time
import datetime

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
import pyclowder.datasets
import pyclowder.geostreams
import terrautils.extractors
import terrautils.betydb

import canopyCover as ccCore
import plotid_by_latlon


# Try several variations on each position field to get all required information
def fetch_md_parts(metadata):
    gantry_x, gantry_y = None, None
    loc_cambox_x, loc_cambox_y = None, None
    fov_x, fov_y = None, None
    ctime = None

    """
        Due to observed differences in metadata field names over time, this method is
        flexible with respect to finding fields. By default each entry for each field
        is checked with both a lowercase and uppercase leading character.
    """

    if 'lemnatec_measurement_metadata' in metadata:
        lem_md = metadata['lemnatec_measurement_metadata']
        if 'gantry_system_variable_metadata' in lem_md and 'sensor_fixed_metadata' in lem_md:
            gantry_meta = lem_md['gantry_system_variable_metadata']
            sensor_meta = lem_md['sensor_fixed_metadata']

            # X and Y position of gantry
            x_positions = ['position x [m]', 'position X [m]']
            for variant in x_positions:
                val = check_field_variants(gantry_meta, variant)
                if val:
                    gantry_x = parse_as_float(val)
                    break
            y_positions = ['position y [m]', 'position Y [m]']
            for variant in y_positions:
                val = check_field_variants(gantry_meta, variant)
                if val:
                    gantry_y = parse_as_float(val)
                    break

            # Sensor location within camera box
            cbx_locations = ['location in camera box x [m]', 'location in camera box X [m]']
            for variant in cbx_locations:
                val = check_field_variants(sensor_meta, variant)
                if val:
                    loc_cambox_x = parse_as_float(val)
                    break
            cby_locations = ['location in camera box y [m]', 'location in camera box Y [m]']
            for variant in cby_locations:
                val = check_field_variants(sensor_meta, variant)
                if val:
                    loc_cambox_y = parse_as_float(val)
                    break

            # Field of view
            x_fovs = ['field of view x [m]', 'field of view X [m]']
            for variant in x_fovs:
                val = check_field_variants(sensor_meta, variant)
                if val:
                    fov_x = parse_as_float(val)
                    break
            y_fovs = ['field of view y [m]', 'field of view Y [m]']
            for variant in y_fovs:
                val = check_field_variants(sensor_meta, variant)
                if val:
                    fov_y = parse_as_float(val)
                    break
            if not (fov_x and fov_y):
                val = check_field_variants(sensor_meta, 'field of view at 2m in X- Y- direction [m]')
                if val:
                    vals = val.replace('[','').replace(']','').split(' ')
                    if not fov_x:
                        fov_x = parse_as_float(vals[0])
                    if not fov_y:
                        fov_y = parse_as_float(vals[1])

            # TODO: Find a better solution once metadata files are fixed
            # TODO: These values from https://github.com/terraref/computing-pipeline/issues/126#issuecomment-292027575
            fov_x = 1.015
            fov_y = 0.749

            # timestamp, e.g. "2016-05-15T00:30:00-05:00"
            val = check_field_variants(gantry_meta, 'time')
            if val:
                ctime = val.encode("utf-8")
            else:
                ctime = "unknown"

    return gantry_x, gantry_y, loc_cambox_x, loc_cambox_y, fov_x, fov_y, ctime

# Check for fieldname in dict, including capitalization changes
def check_field_variants(dict, key):
    if key in dict:
        return dict[key]
    elif key.capitalize() in dict:
        return dict[key.capitalize()]
    else:
        return False

# Try to convert val to float, return val on Exception
def parse_as_float(val):
    try:
        return float(val.encode("utf-8"))
    except AttributeError:
        return val

class CanopyCoverHeight(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        influx_host = os.getenv("INFLUXDB_HOST", "terra-logging.ncsa.illinois.edu")
        influx_port = os.getenv("INFLUXDB_PORT", 8086)
        influx_db = os.getenv("INFLUXDB_DB", "extractor_db")
        influx_user = os.getenv("INFLUXDB_USER", "terra")
        influx_pass = os.getenv("INFLUXDB_PASSWORD", "")

        # add any additional arguments to parser
        # self.parser.add_argument('--max', '-m', type=int, nargs='?', default=-1,
        #                          help='maximum number (default=-1)')
        self.parser.add_argument('--output', '-o', dest="output_dir", type=str, nargs='?',
                                 default="/home/extractor/sites/ua-mac/Level_1/stereoTop_canopyCover",
                                 help="root directory where timestamp & output directories will be created")
        self.parser.add_argument('--overwrite', dest="force_overwrite", type=bool, nargs='?', default=False,
                                 help="whether to overwrite output file if it already exists in output directory")
        self.parser.add_argument('--betyURL', dest="bety_url", type=str, nargs='?',
                                 default="https://terraref.ncsa.illinois.edu/bety/api/beta/traits.csv",
                                 help="traits API endpoint of BETY instance that outputs should be posted to")
        self.parser.add_argument('--betyKey', dest="bety_key", type=str, nargs='?', default=False,
                                 help="API key for BETY instance specified by betyURL")
        self.parser.add_argument('--plots', dest="plots_shp", type=str, nargs='?',
                                 default="/home/extractor/extractors-metadata/sensorposition/shp/sorghumexpfall2016v5/sorghumexpfall2016v5_lblentry_1to7.shp",
                                 help=".shp file containing plots")
        self.parser.add_argument('--influxHost', dest="influx_host", type=str, nargs='?',
                                 default=influx_host, help="InfluxDB URL for logging")
        self.parser.add_argument('--influxPort', dest="influx_port", type=int, nargs='?',
                                 default=influx_port, help="InfluxDB port")
        self.parser.add_argument('--influxUser', dest="influx_user", type=str, nargs='?',
                                 default=influx_user, help="InfluxDB username")
        self.parser.add_argument('--influxPass', dest="influx_pass", type=str, nargs='?',
                                 default=influx_pass, help="InfluxDB password")
        self.parser.add_argument('--influxDB', dest="influx_db", type=str, nargs='?',
                                 default=influx_db, help="InfluxDB database")

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
        self.plots_shp = self.args.plots_shp
        self.influx_params = {
            "host": self.args.influx_host,
            "port": self.args.influx_port,
            "db": self.args.influx_db,
            "user": self.args.influx_user,
            "pass": self.args.influx_pass
        }

    def check_message(self, connector, host, secret_key, resource, parameters):
        if not terrautils.extractors.is_latest_file(resource):
            return CheckMessage.ignore

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
        out_dir = terrautils.extractors.get_output_directory(self.output_dir, resource['dataset_info']['name'])
        if not self.force_overwrite:
            outfile = os.path.join(out_dir, terrautils.extractors.get_output_filename(
                    resource['dataset_info']['name'], 'csv', opts=['canopycover']))
            if os.path.isfile(outfile):
                logging.info("skipping dataset %s, output already exists" % resource['id'])
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
        starttime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        created = 0
        bytes = 0

        # Get left/right files and metadata
        img_left, img_right, metadata = None, None, None, None
        for fname in resource['local_paths']:
            # First check metadata attached to dataset in Clowder for item of interest
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = terrautils.extractors.load_json_file(fname)
                for curr_dsmd in all_dsmd:
                    if 'content' in curr_dsmd and 'lemnatec_measurement_metadata' in curr_dsmd['content']:
                        metadata = curr_dsmd['content']
            # Otherwise, check if metadata was uploaded as a .json file
            elif fname.endswith('_metadata.json') and fname.find('/_metadata.json') == -1 and metadata is None:
                metadata = terrautils.extractors.load_json_file(fname)
            elif fname.endswith('_left.bin'):
                img_left = fname
            elif fname.endswith('_right.bin'):
                img_right = fname
        if None in [img_left, img_right, metadata]:
            raise ValueError("could not locate each of left+right+metadata in processing")

        # Determine output directory
        out_dir = terrautils.extractors.get_output_directory(self.output_dir, resource['dataset_info']['name'])
        logging.info("...writing outputs to: %s" % out_dir)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        outfile = os.path.join(out_dir, terrautils.extractors.get_output_filename(
                resource['dataset_info']['name'], 'csv', opts=['canopycover']))

        if (not os.path.isfile(outfile)) or self.force_overwrite:
            # Get information from input data
            metadata = ccCore.lower_keys(metadata)
            # TODO: Replace this with BETYdb query
            plotNum = ccCore.get_plot_num(metadata)
            ccVal = ccCore.get_CC_from_bin(img_left)

            # get traits and values & generate output CSV
            (fields, traits) = ccCore.get_traits_table()
            str_time = str(ccCore.get_localdatetime(metadata))
            str_date = str_time[6:10]+'-'+str_time[:5]+'T'+str_time[11:]
            traits['local_datetime'] = str_date.replace("/", '-')
            traits['canopy_cover'] = str(ccVal)
            # TODO: Replace with results from BETYdb
            traits['site'] = 'MAC Field Scanner Field Plot '+ str(plotNum)+' Season 2'
            trait_list = ccCore.generate_traits_list(traits)
            ccCore.generate_cc_csv(outfile, fields, trait_list)

            created += 1
            bytes += os.path.getsize(outfile)

        # Only upload the newly generated CSV to Clowder if it isn't already in dataset
        if outfile not in resource['local_paths']:
            csv_id = pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['id'], outfile)
        else:
            csv_id = ""

        # submit CSV to BETY
        terrautils.betydb.submit_traits(outfile, self.bety_key)

        # generate datapoint for geostreams
        self.submitDatapoint(connector, host, secret_key, resource, metadata, fields, trait_list)

        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        metadata = terrautils.extractors.build_metadata(host, self.extractor_info['name'], resource['id'], {
            "files_created": [csv_id]
        }, 'dataset')
        pyclowder.datasets.upload_metadata(connector, host, secret_key, resource['id'], metadata)

        endtime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        terrautils.extractors.log_to_influxdb(self.extractor_info['name'], self.influx_params,
                                              starttime, endtime, created, bytes)

    def submitDatapoint(self, connector, host, secret_key, resource, metadata, trait_names, trait_values):
        logging.info("...submitting datapoint to geostreams")

        left_bounds = terrautils.extractors.calculate_gps_bounds(metadata)[0]
        sensor_latlon = terrautils.extractors.calculate_centroid(left_bounds)
        logging.info("sensor lat/lon: %s" % str(sensor_latlon))

        # Upload data into Geostreams API -----------------------------------------------------
        fileIdList = []
        for f in resource['files']:
            fileIdList.append(f['id'])

        # SENSOR is the plot - try by location first
        sensor_data = pyclowder.geostreams.get_sensors_by_circle(connector, host, secret_key, sensor_latlon[1], sensor_latlon[0], 0.01)
        if not sensor_data:
            plot_info = plotid_by_latlon.plotQuery(self.plots_shp, sensor_latlon[1], sensor_latlon[0])
            plot_name = "Range "+plot_info['plot'].replace("-", " Pass ")
            logging.info("...found plot: "+str(plot_info))
            sensor_data = pyclowder.geostreams.get_sensor_by_name(connector, host, secret_key, plot_name)
            if not sensor_data:
                sensor_id = pyclowder.geostreams.create_sensor(connector, host, secret_key, plot_name, {
                    "type": "Point",
                    "coordinates": [plot_info['point'][1], plot_info['point'][0], plot_info['point'][2]]
                }, {
                    "id": "MAC Field Scanner",
                    "title": "MAC Field Scanner",
                    "sensorType": 4
                }, "Maricopa")
            else:
                sensor_id = sensor_data['id']
        else:
            if len(sensor_data) > 1:
                sensor_id = sensor_data[0]['id']
                plot_name = sensor_data[0]['name']
            else:
                sensor_id = sensor_data['id']
                plot_name = sensor_data['name']

        # STREAM is plot x instrument
        stream_name = "Canopy Cover" + " - " + plot_name
        stream_data = pyclowder.geostreams.get_stream_by_name(connector, host, secret_key, stream_name)
        if not stream_data:
            stream_id = pyclowder.geostreams.create_stream(connector, host, secret_key, stream_name, sensor_id, {
                "type": "Point",
                "coordinates": [sensor_latlon[1], sensor_latlon[0], 0]
            })
        else:
            stream_id = stream_data['id']

        logging.info("posting datapoint to stream %s" % stream_id)
        metadata["source"] = host+"datasets/"+resource['id']
        metadata["file_ids"] = ",".join(fileIdList)

        # Format time properly, adding UTC if missing from Danforth timestamp
        time_obj = time.strptime(ctime, "%m/%d/%Y %H:%M:%S")
        time_fmt = time.strftime('%Y-%m-%dT%H:%M:%S', time_obj)
        if len(time_fmt) == 19:
            time_fmt += "-06:00"

        pyclowder.geostreams.create_datapoint(connector, host, secret_key, stream_id, {
            "type": "Point",
            "coordinates": [sensor_latlon[1], sensor_latlon[0], 0]
        }, time_fmt, time_fmt, metadata)


if __name__ == "__main__":
    extractor = CanopyCoverHeight()
    extractor.start()
