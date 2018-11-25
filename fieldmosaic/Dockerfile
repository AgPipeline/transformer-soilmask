FROM terraref/terrautils:1.4
MAINTAINER Max Burnette <mburnet2@illinois.edu>

# Install any programs needed
RUN useradd -u 49044 extractor \
    && mkdir /home/extractor \
    && chown extractor /home/extractor

RUN wget https://raw.githubusercontent.com/GitHubRGI/geopackage-python/master/Tiling/gdal2tiles_parallel.py \
 && mv gdal2tiles_parallel.py /home/extractor/gdal2tiles_parallel.py \
 && pip install opencv-python

RUN add-apt-repository ppa:ubuntugis/ubuntugis-unstable \
    && apt-get -q -y update \
    && apt-get install -y gdal-bin libsm6 \
    && rm -rf /var/lib/apt/lists/*

# command to run when starting docker
COPY entrypoint.sh extractor_info.json *.py /home/extractor/

USER extractor
ENTRYPOINT ["/home/extractor/entrypoint.sh"]
CMD ["extractor"]

# Setup environment variables. These are passed into the container. You can change
# these to your setup. If RABBITMQ_URI is not set, it will try and use the rabbitmq
# server that is linked into the container. MAIN_SCRIPT is set to the script to be
# executed by entrypoint.sh
ENV RABBITMQ_EXCHANGE="terra" \
    RABBITMQ_VHOST="%2F" \
    RABBITMQ_QUEUE="terra.geotiff.fieldmosaic" \
    MAIN_SCRIPT="terra_fieldmosaic.py" \
    CLOWDER_SPACE="5bdc8f174f0cb2fdaaf3148e"
