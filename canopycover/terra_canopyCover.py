'''
Created on Oct 31, 2016

@author: Zongyang
'''


import os
import logging
import imp
import requests

from config import *
import pyclowder.extractors as extractors

def main():
    global extractorName, messageType, rabbitmqExchange, rabbitmqURL, registrationEndpoints, mountedPaths

    #set logging
    logging.basicConfig(format='%(levelname)-7s : %(name)s -  %(message)s', level=logging.WARN)
    logging.getLogger('pyclowder.extractors').setLevel(logging.INFO)
    logger = logging.getLogger('extractor')
    logger.setLevel(logging.DEBUG)

    # setup
    extractors.setup(extractorName=extractorName,
                     messageType=messageType,
                     rabbitmqURL=rabbitmqURL,
                     rabbitmqExchange=rabbitmqExchange)

    # register extractor info
    extractors.register_extractor(registrationEndpoints)

    #connect to rabbitmq
    extractors.connect_message_bus(extractorName=extractorName,
                                   messageType=messageType,
                                   processFileFunction=process_dataset,
                                   checkMessageFunction=check_message,
                                   rabbitmqExchange=rabbitmqExchange,
                                   rabbitmqURL=rabbitmqURL)

def check_message(parameters):
    # Check for a left and right file before beginning processing
    found_left = False
    found_right = False
    for f in parameters['filelist']:
        if 'filename' in f and f['filename'].endswith('_left.bin'):
            found_left = True
        elif 'filename' in f and f['filename'].endswith('_right.bin'):
            found_right = True

    if not (found_left and found_right):
        return False

    # TODO: re-enable once this is merged into Clowder: https://opensource.ncsa.illinois.edu/bitbucket/projects/CATS/repos/clowder/pull-requests/883/overview
    # fetch metadata from dataset to check if we should remove existing entry for this extractor first
    md = extractors.download_dataset_metadata_jsonld(parameters['host'], parameters['secretKey'], parameters['datasetId'], extractorName)
    found_meta = False
    for m in md:
        if 'agent' in m and 'name' in m['agent']:
            if m['agent']['name'].find(extractorName) > -1:
                print("skipping dataset %s, already processed" % parameters['datasetId'])
                return False
                #extractors.remove_dataset_metadata_jsonld(parameters['host'], parameters['secretKey'], parameters['datasetId'], extractorName)
        # Check for required metadata before beginning processing
        if 'content' in m and 'lemnatec_measurement_metadata' in m['content']:
            found_meta = True

    if found_left and found_right:
        return True
    else:
        return False

def process_dataset(parameters):
    global outputDir

    metafile, img_left, img_right, metadata = None, None, None, None

    # Get left/right files and metadata
    for f in parameters['files']:
        # First check metadata attached to dataset in Clowder for item of interest
        if f.endswith('_dataset_metadata.json'):
            all_dsmd = ccCore.load_json(f)
            for curr_dsmd in all_dsmd:
                if 'content' in curr_dsmd and 'lemnatec_measurement_metadata' in curr_dsmd['content']:
                    metafile = f
                    metadata = curr_dsmd['content']
        # Otherwise, check if metadata was uploaded as a .json file
        elif f.endswith('_metadata.json') and f.find('/_metadata.json') == -1 and metafile is None:
            metafile = f
            metadata = ccCore.load_json(metafile)
        elif f.endswith('_left.bin'):
            img_left = f
        elif f.endswith('_right.bin'):
            img_right = f
    if None in [metafile, img_left, img_right, metadata]:
        ccCore.fail('Could not find all of left/right/metadata.')
        return

    print("...img_left: %s" % img_left)
    print("...img_right: %s" % img_right)
    print("...metafile: %s" % metafile)
    
    dsname = parameters["datasetInfo"]["name"]
    if dsname.find(" - ") > -1:
        timestamp = dsname.split(" - ")[1]
    else:
        timestamp = "dsname"
    if timestamp.find("__") > -1:
        datestamp = timestamp.split("__")[0]
    else:
        datestamp = ""
    out_dir = os.path.join(outputDir, datestamp, timestamp)
    print("...output directory: %s" % out_dir)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    metadata = ccCore.lower_keys(metadata)

    plotNum = ccCore.get_plot_num(metadata)
    
    ccVal = ccCore.get_CC_from_bin(img_left)
    
    # generate output CSV & send to Clowder + BETY
    outfile = os.path.join(outputDir, parameters['datasetInfo']['name'], 'ccTraits.csv')
    print("...output file: %s" % outfile)
    out_dir = outfile.replace(os.path.basename(outfile), "")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    (fields, traits) = ccCore.get_traits_table()
    traits['local_datetime'] = str(ccCore.get_localdatetime(metadata))
    traits['canopy_cover'] = str(ccVal)
    traits['site'] = 'Maricopa Field Scanner Plot '+ str(plotNum)
    trait_list = ccCore.generate_traits_list(traits)
    ccCore.generate_cc_csv(outfile, fields, trait_list)
    extractors.upload_file_to_dataset(outfile, parameters)
    submitToBety(outfile)
    
    # Tell Clowder this is completed so subsequent file updates don't daisy-chain
    metadata = {
        "@context": {
            "@vocab": "https://clowder.ncsa.illinois.edu/clowder/assets/docs/api/index.html#!/files/uploadToDataset"
        },
        "dataset_id": parameters["datasetId"],
        "content": {"status": "COMPLETED"},
        "agent": {
            "@type": "cat:extractor",
            "extractor_id": parameters['host'] + "/api/extractors/" + extractorName
        }
    }
    extractors.upload_dataset_metadata_jsonld(mdata=metadata, parameters=parameters)
    
def submitToBety(csvfile):
    global betyAPI, betyKey

    if betyAPI != "":
        sess = requests.Session()
        print(csvfile)
        print("%s?key=%s" % (betyAPI, betyKey))
        r = sess.post("%s?key=%s" % (betyAPI, betyKey),
                  data=file(csvfile, 'rb').read(),
                  headers={'Content-type': 'text/csv'})

        if r.status_code == 200 or r.status_code == 201:
            print("CSV successfully uploaded to BETYdb.")
        else:
            print("Error uploading CSV to BETYdb %s" % r.status_code)
            print(r.text)

if __name__ == "__main__":
    global getCanopyCoverScript

    # Import canopyCover script from configured location
    ccCore = imp.load_source('canopyCover', getCanopyCoverScript)

    main()
