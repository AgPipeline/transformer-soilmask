# Bin2Tif Extractor

This extractor processes binary stereo images using metadata and outputs JPG and TIFF images.

_Input_

  - Evaluation is triggered whenever a file is added to a dataset
  - Following data must be found
    - _left.bin image
    - _right.bin image
    - dataset metadata for the left+right capture dataset; can be attached as Clowder metadata or included as a metadata.json file

_Output_

  - The dataset containing the left/right binary images will get left/right JPG and TIFF images

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

First, create a Python virtualenv with the relevant dependencies:

```
module load gdal2-stack
module load python/2.7.10
module load pythonlibs/2.7.10
virtualenv terraref --python=python2.7
cd terraref
. bin/activate
git clone https://opensource.ncsa.illinois.edu/stash/scm/cats/pyclowder2.git
pip install  pyclowder2/
git clone https://github.com/terraref/terrautils/
pip install terrautils/
git clone https://github.com/terraref/extractors-stereo-rgb
pip install Pillow enum34 pyyaml pika functools32 pyparsing pytz GDAL
```

Once the virtual environment is configured with pyclowder, terrautils, and the extractor, you can run the batch job.

The following example PBS script requests a 20 core node and runs 20 bin2tif extractors in parallel:
```
#!/bin/bash

#PBS -l walltime=00:05:00
#PBS -l nodes=1:ppn=20
#PBS -q batch
#PBS -j oe
#PBS -o bin2tif.log
#PBS -m be
#PBS -M <your email>

module load parallel
module load gdal2-stack
module load python/2.7.10
module load pythonlibs/2.7.10

. ~/terraref/bin/activate

seq 20 | parallel --ungroup -n0 "~/terraref/bin/python ~/terraref/extractors-stereo-rgb/bin2tif/terra_bin2tif.py"
```


Create an environment file containing the following (e.g., env.sh):
```
export RABBITMQ_URI=
export REGISTRATION_ENDPOINTS=
export RABBITMQ_EXCHANGE=
export CLOWDER_USER=
export CLOWDER_PASS=
export CLOWDER_SPACE
export INFLUXDB_PASSWORD=
```

Run the job:
```
. env.sh
qsub -V bin2tif.pbs
```


### Dependencies

* All the Python scripts syntactically support Python 2.7 and above. Please make sure that the Python in the running environment is in appropriate version.

* All the Python scripts also rely on the third-party library including: PIL, scipy, numpy and osgeo.
