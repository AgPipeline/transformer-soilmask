# Field Mosaic Extractor

Stereo RGB Image metadata to JPG and TIFF Converter.

## Authors:

* Zongyang Li, Donald Danforth Plant Science Center, St. Louis, MO
* Maxwell Burnette, National Supercomputing Applications, Urbana, IL
* Robert Pless, George Washington University, Washington, D.C.

## Overview

This extractor processes binary stereo images using metadata and outputs demosaicked JPG and TIFF images.

_Input_

  - Evaluation is triggered whenever a file is added to a dataset
  - Following data must be found
    - _left.bin image
    - _right.bin image
    - dataset metadata for the left+right capture dataset; can be attached as Clowder metadata or included as a metadata.json file

_Output_

  - The dataset containing the left/right binary images will get left/right JPG and TIFF images

## Algorithm

### Algorithm Description

<TODO>

### Use 

the stitched image, as is, is good for:

#### Evaluating data quality and valid sensor operation

- Understanding what part of the field was imaged,
- Understanding if the imaging script is correctly capturing the plots (in the context of not imaging the whole field), or if there is a problem it is missing some of the plots.
- Understanding if the image capture has good lighting, no motion blur, etc.

#### Data analysis: computing some phenotypes

- an extractor for Canopy Coverage Percentage, and
- an extractor for some other phenotype analyses such as emergence date, leaf color, flower/panacle detection


#### Data analysis: the stitched image is not appropriate for some analyses 

- Any stitched image introduces new artifacts into the image data; it always introduces edges at the boundary of where one image turns into another --- either an explicitly black line boundary or an implicit boundary that is there because you can't exactly stitch images of a complicated 3D world (without making a full 3D model).  Even if you could stitch them (say, it is just flat dirt), the same bit of the world is usually a different brightness when viewed from different directions.
- The particular stitching strategy of "choose the darker pixel" is a nice way to automatically choose a good image when there is bright sunshine effects.  It may create additional artifacts because the algorithm is allowed to integrate pixels from both images in potentially complicated patterns.  These artifacts may be hard to account for.
- The alternative is to always to all initial feature selection or image analysis on the original images, and to then create derived features or extracted features from those images and save those derived or extracted features per plot.

To ground this discussion, here is an example of a stitched image

![picture1](https://user-images.githubusercontent.com/20230686/26936199-916d6b64-4c33-11e7-8544-97294aa97017.png)

see also 'failure conditions' below

## Application

### Docker

The Dockerfile included in this directory can be used to launch this extractor in a container.

_Building the Docker image_

```sh
docker build -f Dockerfile -t terra-ext-bin2tif .
```

_Running the image locally_
```sh
docker run \
  -p 5672 -p 9000 --add-host="localhost:{LOCAL_IP}" \
  -e RABBITMQ_URI=amqp://{RMQ_USER}:{RMQ_PASSWORD}@localhost:5672/%2f \
  -e RABBITMQ_EXCHANGE=clowder \
  -e REGISTRATION_ENDPOINTS=http://localhost:9000/clowder/api/extractors?key={SECRET_KEY} \
  terra-ext-bin2tif
```
Note that by default RabbitMQ will not allow "guest:guest" access to non-local addresses, which includes Docker. You may need to create an additional local RabbitMQ user for testing.

_Running the image remotely_
```sh
docker run \
  -e RABBITMQ_URI=amqp://{RMQ_USER}:{RMQ_PASSWORD}@rabbitmq.ncsa.illinois.edu/clowder \
  -e RABBITMQ_EXCHANGE=terra \
  -e REGISTRATION_ENDPOINTS=http://terraref.ncsa.illinosi.edu/clowder//api/extractors?key={SECRET_KEY} \
  terra-ext-bin2tif
```

### Dependencies

* All the Python scripts syntactically support Python 2.7 and above. Please make sure that the Python in the running environment is in appropriate version.

* All the Python scripts also rely on the third-party library including: PIL, scipy, numpy and osgeo.

## Failure Conditions

### Image Stitching Artifacts
One of the artifacts is duplication of area, this is unavoidable without a much more complex stitching algorithm that implicitly infers the 3D structure of the ground. The justification for not going for such a rich representation is that:
* for the plants, since they move, it would be impossible not to have artifacts at the edges of the image, and
* for the ground, I judged that small stitching errors were not worth the (substantial) additional effort to build the more complete model.

Related Issues and Discussions

* Review of RGB Full Field extractor https://github.com/terraref/reference-data/issues/183
* Dealing with sun/shade https://github.com/terraref/computing-pipeline/issues/326
* Robert Pless https://github.com/terraref/computing-pipeline/issues/326#issuecomment-314895910,
https://github.com/terraref/computing-pipeline/issues/326#issuecomment-314592669, https://github.com/terraref/reference-data/issues/183#issuecomment-330697397

### Planned and Proposed Changes for v1 release

* Use Orthomosaicing to account for 3D structure of the ground terraref/computing-pipeline#355
* Develop pipeline to clip all images in a plot, analyze, and compute plot level summaries https://github.com/terraref/computing-pipeline/issues/356
