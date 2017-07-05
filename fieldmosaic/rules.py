#!/usr/bin/env python

import logging
import subprocess

import rule_utils


# setup logging for the exctractor
logging.getLogger('pyclowder').setLevel(logging.DEBUG)
logging.getLogger('__main__').setLevel(logging.DEBUG)


# This rule can be used with the rulechecker extractor to trigger the fieldmosaic extractor.
# https://opensource.ncsa.illinois.edu/bitbucket/projects/CATS/repos/extractors-rulechecker
def fullFieldMosaicStitcher(extractor, connector, host, secret_key, resource, rulemap):
    results = {}
    full_field_ready = False

    # full-field queues must have at least this percent of the raw datasets present to trigger
    tolerance_pct = 98
    # full-field queues must have at least this many datasets to trigger
    min_datasets = 100

    # Determine output dataset
    dsname = resource["dataset_info"]["name"]
    sensor = dsname.split(" - ")[0]

    if sensor == "stereoTop":
        timestamp = dsname.split(" - ")[1]
        date = timestamp.split("__")[0]
        progress_key = "Full Field - " + sensor + " - " + date

        logging.info("evaluating %s" % progress_key)

        # Is there actually a new left geoTIFF to add to the stack?
        left_id = None
        for f in resource['files']:
            if f['filename'].endswith(" (Left).tif") or f['filename'].endswith("_left.tif"):
                left_id = f['id']
        if not left_id:
            # If not, no need to trigger anything for now.
            logging.info("no left geoTIFF found in %s" % dsname)
            for extractor in rulemap["extractors"]:
                results[extractor] = {
                    "process": False,
                    "parameters": {}
                }
            return results

        # Fetch all existing file IDs that would be fed into this field mosaic
        progress = rule_utils.retrieveProgressFromDB(progress_key)
        if 'ids' in progress:
            if left_id not in progress['ids']:
                progress['ids'] += [left_id]
            else:
                # Already seen this geoTIFF, so skip for now.
                logging.info("previously logged left geoTIFF in %s" % dsname)
                for extractor in rulemap["extractors"]:
                    results[extractor] = {
                        "process": False,
                        "parameters": {}
                    }
                #return results
        else:
            progress['ids'] = [left_id]

        if len(progress['ids']) > min_datasets:
            # Check to see if list of geotiffs is same length as list of raw datasets
            date_directory = "/home/clowder/sites/ua-mac/raw_data/stereoTop/%s" % date
            raw_file_count = float(subprocess.check_output("ls %s | wc -l" % date_directory,
                                                     shell=True).strip())

            # If we have all raw files accounted for and more than 6000 (typical daily magnitude) listed, trigger
            prog_pct = (len(progress['ids'])/raw_file_count)*100
            if prog_pct >= tolerance_pct:
                full_field_ready = True
            else:
                logging.info("found %s/%s necessary geotiffs (%s %%)" % (len(progress['ids']), raw_file_count,
                                                                          "{0:.2f}".format(prog_pct)))

        for extractor in rulemap["extractors"]:
            results[extractor] = {
                "process": full_field_ready,
                "parameters": {
                    "file_ids": progress["ids"]
                }
            }
            if full_field_ready:
                results[extractor]["parameters"]["output_dataset"] = "Full Field - "+date

            rule_utils.submitProgressToDB("fullFieldMosaicStitcher", extractor, progress_key, progress["ids"])

    else:
        for extractor in rulemap["extractors"]:
            results[extractor] = {
                "process": False,
                "parameters": {}
            }

    return results