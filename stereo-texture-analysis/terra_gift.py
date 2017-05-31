#!/usr/bin/env python

"""
terra.gift.py
This extractor will trigger when an image is uploaded into Clowder. It will create csv file which contains the feature vectors.
"""
import os
import logging
import subprocess
import tempfile

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
import pyclowder.datasets



class gift(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the exctractor
        logging.getLogger('pyclowder').setLevel(logging.DEBUG)
        logging.getLogger('__main__').setLevel(logging.DEBUG)
        print "\n 0 \n"

    # Check whether dataset already has metadata
    def check_message(self, connector, host, secret_key, resource, parameters):
        # Check if we have a  file
	
	input_image = None


	
	#print("print resource['local_paths']:%s"%(resource["local_paths"][0]))
	print resource
	print('parameter \n')
	print parameters
	for f in resource['files']:
	    if f['filename'].endswith(".jpg"):
	    	input_image= f['filepath'] #

	if input_image:
            out_dir = input_image.replace(os.path.basename(input_image), "")
            out_name = resource['name'] + "-table.csv"
            out_csv =  os.path.join(out_dir, out_name)
            if os.path.exists(out_csv):
                logging.info("output file already exists; skipping %s" % resource['id'])
            else:
                return CheckMessage.download

	return CheckMessage.ignore

   	
                   
    #def process_message(self, connector, host, secret_key, resource, parameters):
    def process_message(self, connector, host, secret_key, resource, parameters):


	#print parametersdef process_dataset(parameters):
        input_image = None
	print resource
        for p in resource['local_paths']: #
            if p.endswith(".jpg"):
            	input_image = p
	

        print("start processing")
        
	# Create output in same directory as input, but check name
        out_dir = input_image.replace(os.path.basename(input_image), "")
        out_name = resource['name'] + "-table.csv"
        out_csv = os.path.join(out_dir, out_name)



        subprocess.call(['git clone https://github.com/solmazhajmohammadi/gift '], shell=True)
	subprocess.call(['cp -rT /home/extractor/gift .'], shell= True)
	subprocess.call(['chmod 777 gift.R'], shell=True)
        subprocess.call(["Rscript", "gift.R",  "-f", input_image, "-t"])

        if os.path.isfile(out_csv):
            # Send bmp output to Clowder source dataset
            logging.info("uploading %s to dataset" % out_csv)
            pyclowder.files.upload_to_dataset(connector, host, secret_key, resource['parent']['id'], out_csv)


if __name__ == "__main__":
    extractor = gift()
extractor.start()
