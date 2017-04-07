#!/bin/bash


echo "--START     " `date` >&2
echo "---TARGET   " ${@%%.bin} >&2

#rm -f tmp.tif tmp.png tmp-table.csv tmp-dgci.png tmp-edge.png tmp-label.png

#bayer2rgb  -t -i "$@" -o tmp.tif -v  2472 -w 3296 -b 8 -m AHD -f GRBG
#convert tmp.tif tmp.png

#Rscript gift.R -f tmp.png -t
Rscript gift.R -f tmp.png -t -d -e -l  -r roi.png

if [ -e tmp-table.csv ]; then  mv tmp-table.csv ${@%%.bin}-table.csv; fi
if [ -e tmp-dgci.png ]; then  mv tmp-dgci.png ${@%%.bin}-dgci.png; fi
if [ -e tmp-edge.png ]; then  mv tmp-edge.png ${@%%.bin}-edge.png; fi
if [ -e tmp-label.png ]; then  mv tmp-label.png ${@%%.bin}-label.png; fi

echo "---RSCRIPT  " `date` >&2

echo "--END       " `date` >&2


