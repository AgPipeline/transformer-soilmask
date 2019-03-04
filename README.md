# Stereo 3D RGB extractors

This repository contains extractors that process data originating from the GT3300C 8MP RGB Camera.

### Canopy cover extractor
This extractor processes binary stereo images and generates plot-level percentage canopy cover traits for BETYdb.
 
_Input_

  - Evaluation is triggered whenever a file is added to a dataset
  - Following data must be found
    - _left.bin image
    - _right.bin image
    - dataset metadata for the left+right capture dataset; can be attached as Clowder metadata or included as a metadata.json file
    
_Output_

  - CSV with canopy coverage traits will be added to original dataset in Clowder
  - The configured BETYdb instance will have canopy coverage traits inserted

### Full field mosaic stitching extractor

This extractor takes a day of stereo BIN files and creates tiled JPG/TIFF images as well as a map HTML page.

_Input_

  - Currently this should be run on Roger as a job. Date is primary parameter.

### Stereo Texture Analysis

Computes geometric and texture properties using the [computeFeatures](https://rdrr.io/bioc/EBImage/man/computeFeatures.html) functions in the EBImage R package 

### RGB image quality enhancement extractor
This extractor is designed to improve the RGB image (Gantry or UAS imaging systems) quality in term of visualization from four different aspects: illumination, contrast, noise, and color.

