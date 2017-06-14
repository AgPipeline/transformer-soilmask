FROM terraref/terrautils
MAINTAINER Solmaz Hajmohammadi <Solmaz.hajmohammadi@lemanatec.de>

# Install any programs needed
RUN useradd -u 49044 extractor \
    && mkdir -p /home/extractor/sites/ua-mac/raw_data \
    && mkdir -p /home/extractor/sites/ua-mac/Level_1/stereoTop_geotiff \
    && mkdir -p /home/extractor/sites/ua-mac/Level_1/texture_analysis \
    && chown -R extractor /home/extractor

RUN apt-get update \ 
    && apt-get install -y  ed \
        less \
        locales \
        vim-tiny \
        wget \
        ca-certificates \
        fonts-texgyre \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends  \
        bzip2 \
        unzip \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    sudo \
    pandoc \
    pandoc-citeproc \
    libcurl4-gnutls-dev \
    libcairo2-dev \
    libxt-dev \
    libssl-dev \
    libssh2-1-dev \
    libssl1.0.0

RUN apt-get install -y python-pip git python-dev
RUN pip install cython
RUN pip install numpy


# system library dependency for the euler app
RUN apt-get update && apt-get install -y \
    libmpfr-dev
RUN sudo apt-get install -y \
    r-base r-base-dev libcurl4-openssl-dev

# basic shiny functionality
RUN R -e "install.packages(c('shiny', 'rmarkdown'), repos='https://cloud.r-project.org/')"

# install dependencies
RUN R -e "install.packages('Rmpfr', repos='https://cloud.r-project.org/')"

# Special Package for EBImage
RUN apt-get update -y
RUN apt-get install -y libfftw3-dev --fix-missing
RUN apt-get install -y libtiff5-dev --fix-missing

RUN R -e "install.packages(c('tiff'), dep=TRUE, repos='http://cran.rstudio.com')"

RUN Rscript -e 'source("http://bioconductor.org/biocLite.R")' -e 'biocLite("EBImage")'

RUN R -e "install.packages('devtools', repos='https://cloud.r-project.org/')"
RUN R -e "install.packages('getopt', repos='https://cloud.r-project.org/')"
RUN R -e "install.packages('optparse', repos='https://cloud.r-project.org/')"
RUN R -e "install.packages('plyr', repos='https://cloud.r-project.org/')"
RUN R -e "install.packages('dplyr', repos='https://cloud.r-project.org/')"


RUN apt-get update && apt-get install -y --no-install-recommends r-base r-base-dev \
                              libcurl4-openssl-dev libssl-dev git && \
    echo 'options("repos"="http://cran.rstudio.com", download.file.method = "libcurl")' >> /etc/R/Rprofile.site && \
    R -e "install.packages(c('doSNOW','plotrix','getopt','optparse'))" && \
    apt-get purge -y r-base-dev git libcurl4-openssl-dev libssl-dev && \
    apt-get -y clean && apt-get -y autoremove && rm -rf /var/lib/{cache,log}/ /tmp/* /var/tmp/*

RUN Rscript -e 'source("http://bioconductor.org/biocLite.R")' -e 'biocLite()' -e 'biocLite("EBImage")'

##setup R configs
#RUN echo "r <- getOption('repos'); r['CRAN'] <- 'http://cran.us.r-project.org'; options(repos = r);" > ~/.Rprofile

#getopt
RUN  R -e "install.packages('getopt', dependencies=TRUE, repos='http://cran.rstudio.com/')"

RUN apt-get update && apt-get install -y \ 
    wget \
    build-essential \ 
    cmake \ 
    git \
    unzip

# IMAGEMAGICK  
RUN apt-get install libgtk-3-dev -y
RUN  apt-get install imagemagick --fix-missing -y

# command to run when starting docker
COPY entrypoint.sh extractor_info.json *.py gift.R bayer2rgb-master /home/extractor/

USER extractor
ENTRYPOINT ["/home/extractor/entrypoint.sh"]
CMD ["extractor"]

# Setup environment variables. These are passed into the container. You can change
# these to your setup. If RABBITMQ_URI is not set, it will try and use the rabbitmq
# server that is linked into the container. MAIN_SCRIPT is set to the script to be
# executed by entrypoint.sh
ENV RABBITMQ_EXCHANGE="terra" \
    RABBITMQ_VHOST="%2F" \
    RABBITMQ_QUEUE="terra.gift" \
    RABBITMQ_URI="" \
MAIN_SCRIPT="terra_gift.py"
