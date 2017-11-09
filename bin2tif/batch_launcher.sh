#!/bin/bash
# this script is called to invoke one instance of bin2tif extractor.

#PBS -l walltime=48:00:00
#PBS -l nodes=1:ppn=20
#PBS -q
#PBS -j oe
#PBS -o /projects/arpae/terraref/shared/extractors/logs/bin2tif.log
#PBS -m be
#PBS -M <your email>

# Load necessary modules
module purge
module load python/2.7.10 pythonlibs/2.7.10 gdal-stack-2.7.10 gdal netcdf parallel

# Activate python virtualenv
source /projects/arpae/terraref/shared/extractors/pyenv/bin/activate
source /projects/arpae/terraref/shared/extractors/env.sh

export RABBITMQ_VHOST=%2F
export RABBITMQ_QUEUE=terra.stereo-rgb.bin2tif

# Run the same number of python processes as specified in PPN
seq 20 | parallel --nogroup -n0 python /projects/arpae/terraref/shared/extractors/extractors-stereo-rgb/bin2tif/terra_bin2tif.py
