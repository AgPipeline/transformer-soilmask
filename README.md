# Stereo 3D RGB extractors

This repository contains extractors that process data originating from the GT3300C 8MP RGB Camera.


### Demosaic extractor
This extractor processes binary stereo images using metadata and outputs demosaicked JPG and TIFF images.

_Input_

  - Evaluation is triggered whenever a file is added to a dataset
  - Following data must be found
    - _left.bin image
    - _right.bin image
    - _dataset_metadata.json file, representing metadata for the left+right capture dataset

_Output_

  - The dataset containing the left/right binary images will get left/right JPG and TIFF images
