FROM terraref/terrautils:1.4
MAINTAINER Max Burnette <mburnet2@illinois.edu>

# Install any programs needed
RUN useradd -u 49044 extractor

RUN pip install terraref-stereo-rgb \
                opencv-python \
                Pillow \
                scikit-image
RUN apt update && apt install -y libsm6 \
                                libxext6 \
                                libxrender-dev \
                                python-matplotlib \
                                python-numpy \
                                python-pil \
                                python-scipy \
                                build-essential \
                                cython

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
    RABBITMQ_QUEUE="terra.stereo-rgb.rgbmask" \
    MAIN_SCRIPT="terra_rgbmask.py"
