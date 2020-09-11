FROM ubuntu:18.04
LABEL maintainer="Chris Schnaufer <schnaufer@email.arizona.edu>"

# Add user
RUN useradd -u 49044 extractor \
    && mkdir /home/extractor
RUN chown -R extractor /home/extractor \
    && chgrp -R extractor /home/extractor

# Install the Python version we want
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        python3.7 \
        python3-pip && \
    ln -sfn /usr/bin/python3.7 /usr/bin/python && \
    ln -sfn /usr/bin/python3.7 /usr/bin/python3 && \
    ln -sfn /usr/bin/python3.7m /usr/bin/python3m && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Perform some upgrades
RUN python3 -m pip install --upgrade --no-cache-dir pip
RUN python3 -m pip install --upgrade --no-cache-dir setuptools

# Install applications we need
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-gdal \
        gdal-bin   \
        libgdal-dev  \
        gcc \
        g++ \
        python3.7-dev && \
    python3 -m pip install --upgrade --no-cache-dir \
        wheel && \
    python3 -m pip install --upgrade --no-cache-dir \
        numpy && \
    python3 -m pip install --upgrade --no-cache-dir \
        pygdal==2.2.3.* && \
    apt-get remove -y \
        libgdal-dev \
        gcc \
        g++ \
        python3-dev && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Start installing things
COPY requirements.txt packages.txt /home/extractor/

USER root

RUN [ -s /home/extractor/packages.txt ] && \
    (echo 'Installing packages' && \
        apt-get update && \
        cat /home/extractor/packages.txt | xargs apt-get install -y --no-install-recommends && \
        rm /home/extractor/packages.txt && \
        apt-get autoremove -y && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*) || \
    (echo 'No packages to install' && \
        rm /home/extractor/packages.txt)

RUN [ -s /home/extractor/requirements.txt ] && \
    (echo "Install python modules" && \
    python3 -m pip install -U --no-cache-dir pip && \
    python3 -m pip install --no-cache-dir setuptools && \
    python3 -m pip install --no-cache-dir -U -r /home/extractor/requirements.txt && \
    rm /home/extractor/requirements.txt) || \
    (echo "No python modules to install" && \
    rm /home/extractor/requirements.txt)

USER extractor
COPY configuration.py soilmask.py /home/extractor/

USER root
RUN chmod a+x /home/extractor/soilmask.py

USER extractor
ENTRYPOINT ["/home/extractor/soilmask.py"]

