# GIFT - a tool to extract green index based features

This tool extracts color and texture features from an RGB image.
The color image is converted into a dark green color indexed (DGCI) image
and the distribution of indexed value computed as intensity histogram.
Texture analysis is done by finding edges within the DGCI image and then
counting the edge pixels.


This is a bash shell script that was tested on 

    No LSB modules are available.
    Distributor ID: Ubuntu
    Description:    Ubuntu 12.04.5 LTS
    Release:        12.04
    Codename:       precise



## Getting Started

use gift.sh to process a single .raw image file.

For example


    ./gift.sh  SamplePlant_Whitetarget/stereoTop/2016-04-30__08-57-55-804/8b924dc8-0500-4dc1-846b-b82bebb9c94f_left.bin

To process a batch of images try the following command

    find . -name "*.bin" | xargs -i ./gift.sh {}


The .bin file (raw image) is converted into a color image using two helper tools (cf prerequisites).
Then the output tmp.png is pass over to gift.R script.
The extraction of image features is done via R, and the output can be modified using the command line options.
Try this

    Rscript gift.R -h



## Output

There four different output available with gift.R, each can be enable|disabled;  per default no output is 
returned!

-table.csv
  This file contains the feature vectors per image or region of interest. Following fields are available:

  - roi = label of region of interest [1..N]
  - area = area of count of pixelsROI
  - edges = 
  - dgci.-0.1 .. dgci.2.9 = histogram bins ranging from DGCI values -.1 to 2.9;  the values represent 
    frequency counts
  - m.cx = center of mass x coordinate
  - m.cy = center of mass y coordinate
  - m.majoraxis = 
  - m.eccentricity = eccentricity of shape
  - m.theta =
  - s.area = area of region of interest
  - s.perimeter = perimeter of shape
  - s.radius.mean = mean radius of shape
  - s.radius.sd = standard deviation of mean radius
  - s.radius.min = minimal radius
  - s.radius.max = maximal radius


-dgci.png
  This is the dark green color indexed image of the original color image.

-edge.png
  On the basis of the DGCI-image, sharp edges are detected and represented as white pixels in the output
  b/w image.

-label.png
  If an image mask with region of interest (ROI) was used, then this output represent the labeled ROIs.


### Prerequisites

Several tools are necessary to run this script:-

- bayer2rgb [https://github.com/jdthomas/bayer2rgb]
- imagemagick [https://www.imagemagick.org/script/index.php]
- R [https://cran.r-project.org/]
  - R libraries:-
    - EBImage [https://bioconductor.org/packages/release/bioc/html/EBImage.html]
    - dplyr [https://cran.r-project.org/web/packages/dplyr/index.html]
    - optparse [https://cran.r-project.org/web/packages/optparse/index.html]


### Installing

Depending on your linux distribution use the repository to install the packages.
For example on ubuntu do

    sudo apt-get install imagemagick

    sudo apt-get install r-baes r-baes-core

To install bayer2rgb follow the installation instructions in the corresponding README file

For all the R libraries use the following:

    R>  install.packages("devtools", dependent=T)
    R>  install.packages("optparse", dependent=T)

Else download the packages from the CRAN repository and issue the following shell command

    R CMD INSTALL dplyr*.tar.gz

To install EBImage follow the instructions from the host webpage (cf link above)


### Running the tests

- check that bayer2rgb works

    bayer2rgb  -t -i gift-test.bin"$@" -o gift-test.tif -v  2472 -w 3296 -b 8 -m AHD -f GRBG

- check that tif to png works with imagemagick's convert tool

    convert gift-test.tif gift-test.png  ### some warning messages may pop up.--> convert.im6: gift-test.tif: Can not read TIFF directory count. `TIFFFetchDirectory' @ error/tiff.c/TIFFErrors/508. convert.im6: Failed to read directory at offset 488513821. `TIFFReadDirectory' @ error/tiff.c/TIFFErrors/508.


- check that gift.R works

    Rscript gift.R -h

    Rscript gift.R -f gift-test.png -t ### should return a tmp-table.csv file --> Error in cbind_all(x) : cannot convert object to a data frame Calls: %>% ... <Anonymous> -> cbind -> cbind -> bind_cols -> cbind_all -> .Call Execution halted

    Rscript gift.R -f gift-test.png -t -d -e -l ### should return all output files --> Error in cbind_all(x) : cannot convert object to a data frame Calls: %>% ... <Anonymous> -> cbind -> cbind -> bind_cols -> cbind_all -> .Call Execution halted



    Rscript gift.R -f gift-test.png -t -r roi.png ### this analysis the image using a b/w image as ROI mask

- finally check that gift.sh works

    ./gift.sh  gift-test.bin


## Authors
Kevin Nagel / kevin.nagel@lemnatec.com

2017-03-23
