FROM agpipeline/gantry-base-image:latest
LABEL maintainer="Chris Schnaufer <schnaufer@email.arizona.edu>"

COPY configuration.py transformer.py requirements.txt packages.txt /home/extractor/

USER root

RUN apt-get update && \
    cat /home/extractor/packages.txt | xargs apt-get install -y --no-install-recommends && \
    rm /home/extractor/packages.txt && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*    

RUN python3 -m pip install --no-cache-dir -r /home/extractor/requirements.txt && \
    rm /home/extractor/requirements.txt

USER extractor
