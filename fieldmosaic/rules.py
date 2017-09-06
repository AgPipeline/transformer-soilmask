#!/usr/bin/env python

import os
import logging
import subprocess
import json

import rule_utils
from terrautils.sensors import Sensors


# setup logging for the exctractor
logging.getLogger('pyclowder').setLevel(logging.DEBUG)
logging.getLogger('__main__').setLevel(logging.DEBUG)


# This rule can be used with the rulechecker extractor to trigger the fieldmosaic extractor.
# https://opensource.ncsa.illinois.edu/bitbucket/projects/CATS/repos/extractors-rulechecker
def fullFieldMosaicStitcher(extractor, connector, host, secret_key, resource, rulemap):
    results = {}
    full_field_ready = False

    # full-field queues must have at least this percent of the raw datasets present to trigger
    tolerance_pct = 99
    # full-field queues must have at least this many datasets to trigger
    min_datasets = 7900

    # Determine output dataset
    dsname = resource["dataset_info"]["name"]
    sensor = dsname.split(" - ")[0]

    # Map sensor display names to the GeoTIFF stitching target in those sensor datasets,
    # including directory to look for date subfolder to count # of datasets on that date
    if os.path.exists('/projects/arpae/terraref/sites'):
        TERRAREF_BASE = '/projects/arpae/terraref/sites'
    elif os.path.exists('/home/clowder/sites'):
        TERRAREF_BASE = '/home/clowder/sites'
    else:
        TERRAREF_BASE = '/home/extractor/sites'

    sensor_lookup = Sensors(TERRAREF_BASE, 'ua-mac')
    stitchable_sensors = {
        sensor_lookup.get_display_name('rgb_geotiff'): {
            "target": "_left.tif",
            "raw_dir": os.path.join(*(sensor_lookup.get_sensor_path('', sensor='stereoTop').split("/")[:-2]))
        },
        sensor_lookup.get_display_name('ir_geotiff'): {
            "target": ".tif",
            "raw_dir": os.path.join(*(sensor_lookup.get_sensor_path('', sensor='flirIrCamera').split("/")[:-2]))
        },
        # TODO: How to handle east/west of heightmap stitching?
        sensor_lookup.get_display_name('laser3d_heightmap'): {
            "target": "_west.tif",
            "raw_dir": os.path.join(*(sensor_lookup.get_sensor_path('', sensor='scanner3DTop').split("/")[:-2]))
        }
    }

    if sensor in stitchable_sensors.keys():
        timestamp = dsname.split(" - ")[1]
        date = timestamp.split("__")[0]
        progress_key = "Full Field -- " + sensor + " - " + date

        # Is there actually a new left geoTIFF to add to the stack?
        target_id = None
        for f in resource['files']:
            if f['filename'].endswith(stitchable_sensors[sensor]["target"]):
                target_id = f['id']
        if not target_id:
            # If not, no need to trigger anything for now.
            logging.info("no target geoTIFF found in %s" % dsname)
            for trig_extractor in rulemap["extractors"]:
                results[trig_extractor] = {
                    "process": False,
                    "parameters": {}
                }
            return results

        logging.info("[%s] found target: %s" % (progress_key, target_id))

        # Fetch all existing file IDs that would be fed into this field mosaic
        progress = rule_utils.retrieveProgressFromDB(progress_key)
        if 'ids' in progress:
            if target_id not in progress['ids']:
                progress['ids'] += [target_id]
            else:
                # Already seen this geoTIFF, so skip for now.
                logging.info("previously logged target geoTIFF from %s" % dsname)
                for trig_extractor in rulemap["extractors"]:
                    results[trig_extractor] = {
                        "process": False,
                        "parameters": {}
                    }
        else:
            progress['ids'] = [target_id]

        if len(progress['ids']) >= min_datasets:
            # Check to see if list of geotiffs is same length as list of raw datasets
            root_dir = stitchable_sensors[sensor]["raw_dir"]
            if len(connector.mounted_paths) > 0:
                for source_path in connector.mounted_paths:
                    if root_dir.startswith(source_path):
                        root_dir = root_dir.replace(source_path, connector.mounted_paths[source_path])
            date_directory = os.path.join(root_dir, date)
            date_directory = ("/"+date_directory if not date_directory.startswith("/") else "")

            raw_file_count = float(subprocess.check_output("ls %s | wc -l" % date_directory,
                                                           shell=True).strip())
            logging.info("found %s raw files in %s" % (int(raw_file_count), date_directory))

            # If we have enough raw files accounted for and more than min_datasets, trigger
            prog_pct = (len(progress['ids'])/raw_file_count)*100
            if prog_pct >= tolerance_pct:
                full_field_ready = True
            else:
                logging.info("found %s/%s necessary geotiffs (%s%%)" % (len(progress['ids']), int(raw_file_count),
                                                                        "{0:.2f}".format(prog_pct)))
        for trig_extractor in rulemap["extractors"]:
            results[trig_extractor] = {
                "process": full_field_ready,
                "parameters": {}
            }
            if full_field_ready:
                results[trig_extractor]["parameters"]["output_dataset"] = "Full Field - "+date

                # Write output ID list to a text file
                output_dir = os.path.dirname(sensor_lookup.get_sensor_path(date, 'fullfield'))
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                output_file = os.path.join(output_dir, sensor+"_file_ids.json")
                with open(output_file, 'w') as out:
                    json.dump(progress["ids"], out)
                results[trig_extractor]["parameters"]["file_ids"] = output_file

            rule_utils.submitProgressToDB("fullFieldMosaicStitcher", trig_extractor, progress_key, progress["ids"])

    else:
        for trig_extractor in rulemap["extractors"]:
            results[trig_extractor] = {
                "process": False,
                "parameters": {}
            }

    return results