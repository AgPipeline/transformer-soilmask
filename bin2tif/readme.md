# Bin2Tif Extractor

## Overview
This extractor processes binary stereo images using metadata and outputs JPG and TIFF images.

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

1. Convert raw data to 3 channels color image

   Stereo RGB camera use a single charge-coupled device(CCD) sensor, with the CCD pixels preceded in the optical path by a color filter array(CFA) in a Bayer mosaic pattern. For each 2x2 set of pixels, two diagonally opposed pixels have green filters, and the other two have red and blue filters. We are assuming it’s in a GBRG ordering, then use bilinear interpolation to do the demosaicing. That means three color planes are independently interpolated using symmetric bilinear interpolation from the nearest neighbors of the same color.

**Reference: Malvar, H.S., L. He, and R. Cutler, High quality linear interpolation for demosaicing of Bayer-patterned color images. ICASPP, Volume 34, Issue 11, pp. 2274-2282, May 2004.**

2. Steps for geo-referencing bounding box to each image.

   a. Get image shape from metadata,

   b. Get camera center position from metadata

   c. Compute field of view for the image
   ```
       i. The JSON data reports the camera field of view as "the field of view for a scene 2 meters away is: “0.749m x 1.015m"

       ii. Predict fov for each image should be:

                  fix_fov = fov_in_2_meter*(camera_height/2)

       iii. In implementing the stitching process, we required two magic numbers that are computed experimentally to get the correct geometric alignment.  Our experimentally determined values are:

           HEIGHT_MAGIC_NUMBER = 1.64

           PREDICT_MAGIC_SLOPE = 0.574

           And they are used in the following way:

		            predict_plant_height = PREDICT_MAGIC_SLOPE * camHeight

		            camH_fix = camHeight + HEIGHT_MAGIC_NUMBER - predict_plant_height

		            fix_fov_x = fov_x*(camH_fix/2)

		            fix_fov_y = fov_y*(camH_fix/2)
   ```
   d. Compute geo-reference bounding box
   ```
        i. Convert coordinates from Scanalyzer to MAC coordinates using formula from [https://terraref.gitbooks.io/terraref-documentation/content/user/geospatial-information.html](https://terraref.gitbooks.io/terraref-documentation/content/user/geospatial-information.html)

        ii. Use utm tools to convert coordinates from MAC to lat/lon
   ```
   e. Using osgeo.gdal, associate with geo-bounding box, create geotiff.

### Parameters

HEIGHT_MAGIC_NUMBER and PREDICT_MAGIC_SLOPE were applied when we estimate the field of view, this is a testing based number.

The geo-reference bounding box is based on an assumption that image is aligned to geographic coordinates, so that moving up in the image corresponds to moving exactly north.

### Limitations

1. Any stitched image introduces new artifacts into the image data; it always introduces edges at the boundary of where one image turns into another --- either an explicitly black line boundary or an implicit boundary that is there because you can't exactly stitch images of a complicated 3D world (without making a full 3D model). Even if you could stitch them, the same bit of the world is usually a different brightness when viewed from different directions.

2. The stitched full field image may have artifacts that arise from harsh shadows in some imaging conditions.

3. One of the artifacts is duplication of area, this is unavoidable without a much more complex stitching algorithm that implicitly infers the 3D structure of the ground. The justification for not going for such a rich representation is that:

    1. for the plants, since they move, it would be impossible not to have artifacts at the edges of the image, and

    2. for the ground, we judged that small stitching errors were not worth the (substantial) additional effort to build the more complete model.

### Failure Conditions

* If the camera is moved in the gantry box, then the magic numbers may have to be recalculated or experimentally determined.

* If the camera is not aligned north-south, then the geo-bounding box may not be accurate.


## Implementation
### Docker
The Dockerfile included in this directory can be used to launch this extractor in a container.

_Building the Docker image_
```
docker build -f Dockerfile -t terra-ext-bin2tif .
```

_Running the image locally_
```
docker run \
  -p 5672 -p 9000 --add-host="localhost:{LOCAL_IP}" \
  -e RABBITMQ_URI=amqp://{RMQ_USER}:{RMQ_PASSWORD}@localhost:5672/%2f \
  -e RABBITMQ_EXCHANGE=clowder \
  -e REGISTRATION_ENDPOINTS=http://localhost:9000/clowder/api/extractors?key={SECRET_KEY} \
  terra-ext-bin2tif
```
Note that by default RabbitMQ will not allow "guest:guest" access to non-local addresses, which includes Docker. You may need to create an additional local RabbitMQ user for testing.

_Running the image remotely_
```
docker run \
  -e RABBITMQ_URI=amqp://{RMQ_USER}:{RMQ_PASSWORD}@rabbitmq.ncsa.illinois.edu/clowder \
  -e RABBITMQ_EXCHANGE=terra \
  -e REGISTRATION_ENDPOINTS=http://terraref.ncsa.illinosi.edu/clowder//api/extractors?key={SECRET_KEY} \
  terra-ext-bin2tif
```

### TORQUE/PBS
The extractor can also be run on ROGER via the TORQUE/PBS batch system.

This process assumes that you are using the existing Python virtualenv under:
```
/projects/arpae/terraref/shared/extractors/pyenv/
```

This also uses a shared environment file for common settings:
```
/projects/arpae/terraref/shared/extractors/env.sh
```

The following default batch jobs will start 20 extractors on a single 20-core node:
```
qsub /projects/arpae/terraref/shared/extractors/extractors-stereo-rgb/bin2tif/batch_launcher.sh
```


### Dependencies

* All the Python scripts syntactically support Python 2.7 and above. Please make sure that the Python in the running environment is in appropriate version.

* All the Python scripts also rely on the third-party library including: PIL, scipy, numpy and osgeo.

