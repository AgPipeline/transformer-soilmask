#!/bin/bash
# this script is called to invoke one instance of full field mosaic stitching processor.

# Load necessary modules
module purge
module load python/2.7.10 pythonlibs/2.7.10 gdal-stack

# Activate python virtualenv
source /projects/arpae/terraref/shared/extractors/pyenv/bin/activate

# Run extractor script
python /projects/arpae/terraref/shared/extractors/extractors-stereo-rgb/mosaic/terra_mosaic.py --date $1
