'''
Created on Aug 5, 2016

@author: Zongyang Li
'''
import os
import logging
import geotiff_to_tiles
import multiprocessing

from config import *
import pyclowder.extractors as extractors

def main():
    global extractorName, messageType, rabbitmqExchange, rabbitmqURL, registrationEndpoints

    #set logging
    logging.basicConfig(format='%(levelname)-7s : %(name)s -  %(message)s', level=logging.WARN)
    logging.getLogger('pyclowder.extractors').setLevel(logging.INFO)

    #connect to rabbitmq
    extractors.connect_message_bus(extractorName=extractorName, messageType=messageType, processFileFunction=process_dataset,
                                   checkMessageFunction=check_message, rabbitmqExchange=rabbitmqExchange, rabbitmqURL=rabbitmqURL)

def check_message(parameters):
    # TODO: re-enable once this is merged into Clowder: https://opensource.ncsa.illinois.edu/bitbucket/projects/CATS/repos/clowder/pull-requests/883/overview
    # fetch metadata from dataset to check if we should remove existing entry for this extractor first
    md = extractors.download_dataset_metadata_jsonld(parameters['host'], parameters['secretKey'], parameters['datasetId'], extractorName)
    for m in md:
        if 'agent' in m and 'name' in m['agent']:
            if m['agent']['name'].find(extractorName) > -1:
                print("skipping, already done")
                return False
                #extractors.remove_dataset_metadata_jsonld(parameters['host'], parameters['secretKey'], parameters['datasetId'], extractorName)

    return True

def process_dataset(parameters):
    tifflist = None

    # Get tif_list from parameters
    for f in parameters['files']:
        if f.endswith('tif_list.txt'):
            tifflist = f;
        
    if None in [tifflist]:
        geotiff_to_tiles.fail('Could not find tif file list')
        return

    # provide an output folder
    print("tiflist: %s" % tifflist)
    temp_out_dir = tifflist.replace(os.path.basename(tifflist), "")
    #test folder
    #temp_out_dir = '/Users/nijiang/Desktop/pythonTest/clowder3/'
    if not os.path.exists(temp_out_dir):
            os.makedirs(temp_out_dir)
    print("base dir: %s" % temp_out_dir)
    upper_dir = os.path.abspath(os.path.join(os.path.dirname(temp_out_dir), os.path.pardir))


    # Create VRT from every GeoTIFF
    print "Starting VRT creation..."
    geotiff_to_tiles.createVrt(temp_out_dir,tifflist)
    print "Completed VRT creation..."


    # Generate tiles from VRT
    print "Starting map tile creation..."
    geotiff_to_tiles.createMapTiles(temp_out_dir,multiprocessing.cpu_count())
    print "Completed map tile creation..."

    # Generate google map html template
    print "Starting google map html creation..."
    geotiff_to_tiles.generate_googlemaps(temp_out_dir)
    print "Completed google map html creation..."
    
    print("Uploading output html to dataset")
    #html_out = os.path.join(temp_out_dir, 'opengooglemaps.html')
    
    zip_out = os.path.join(upper_dir, 'tiles.zip')
    geotiff_to_tiles.make_zip(temp_out_dir, zip_out)
    
    extractors.upload_file_to_dataset(zip_out, parameters)

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

if __name__ == "__main__":

    main()