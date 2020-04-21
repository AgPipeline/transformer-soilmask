#FROM phusion/baseimage
FROM agdrone/transformer-opendronemap:3.0
# Env variables
ENV DEBIAN_FRONTEND noninteractive

COPY transformer_class.py configuration.py entrypoint.py /scif/apps/soilmask/src/
COPY transformer.py /scif/apps/soilmask/src/
# Install the filesystem from the recipe
COPY *.scif /
RUN scif install /recipe.scif

# Cleanup APT
#RUN apt-get clean \
#  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# SciF Entrypoint
ENTRYPOINT ["scif"]