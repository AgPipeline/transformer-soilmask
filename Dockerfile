FROM phusion/baseimage
# Env variables
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update -y \
    && apt-get install --no-install-recommends -y \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh \
    && bash miniconda.sh -b
RUN  ~/miniconda3/bin/conda update -n base -c defaults conda
COPY . /scif/apps/soilmask/src/

# Install the filesystem from the recipe
COPY *.scif /
RUN scif install /recipe.scif

# Cleanup APT
RUN apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# SciF Entrypoint
ENTRYPOINT ["scif"]