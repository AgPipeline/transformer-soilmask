# Stereo 3D RGB extractors

This repository contains extractors that process data originating from the GT3300C 8MP RGB Camera.


### Demosaic extractor
This extractor processes binary stereo images using metadata and outputs demosaicked JPG and TIFF images.

_Input_

  - Evaluation is triggered whenever a file is added to a dataset
  - Following data must be found
    - _left.bin image
    - _right.bin image
    - dataset metadata for the left+right capture dataset; can be attached as Clowder metadata or included as a metadata.json file

_Output_

  - The dataset containing the left/right binary images will get left/right JPG and TIFF images

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


## Known Issues and Assumptions

### Image Stitching Artifacts

The current stitched image is suitable for most data quality and coverage assessments and some data analysis. I'm not sure that any simple stitching process (or any more complicated process that would be called stitching) is good enough to be used for more complicated analysis.

For data quality, the stitched image, as is, is good for:

Understanding what part of the field was imaged,
Understanding if the imaging script is correctly capturing the plots (in the context of not imaging the whole field), or if there is a problem it is missing some of the plots.
Understanding if the image capture has good lighting, no motion blur, etc.
For data analysis, the stitched image, as is, is good for:

an extractor for Canopy Coverage Percentage, and
an extractor for some phenotype analysis (emergence date, leaf color, flower/panacle detection)
For some data analysis, the stitched image will cause some problems. To ground this discussion, here is an example of a stitched image:

Any stitched image introduces new artifacts into the image data; it always introduces edges at the boundary of where one image turns into another --- either an explicitly black line boundary or an implicit boundary that is there because you can't exactly stitch images of a complicated 3D world (without making a full 3D model). Even if you could stitch them (say, it is just flat dirt), the same bit of the world is usually a different brightness when viewed from different directions.

The particular stitching strategy of "choose the darker pixel" is a nice way to automatically choose a good image when there is bright sunshine effects. It may create additional artifacts because the algorithm is allowed to integrate pixels from both images in potentially complicated patterns. These artifacts may be hard to account for.

The alternative is to always to all initial feature selection or image analysis on the original images, and to then create derived features or extracted features from those images and save those derived or extracted features per plot.

One of the artifacts is duplication of area, this is unavoidable without a much more complex stitching algorithm that implicitly infers the 3D structure of the ground. The justification for not going for such a rich representation is that:
* for the plants, since they move, it would be impossible not to have artifacts at the edges of the image, and
* for the ground, I judged that small stitching errors were not worth the (substantial) additional effort to build the more complete model.

- Robert Pless https://github.com/terraref/computing-pipeline/issues/326#issuecomment-314895910,
https://github.com/terraref/computing-pipeline/issues/326#issuecomment-314592669, https://github.com/terraref/reference-data/issues/183#issuecomment-330697397

Related Issues and Discussions

* Review of RGB Full Field extractor https://github.com/terraref/reference-data/issues/183
* Dealing with sun/shade https://github.com/terraref/computing-pipeline/issues/326

### Planned and Proposed Changes

* Use Orthomosaicing to account for 3D structure of the ground terraref/computing-pipeline#355
* Develop pipeline to clip all images in a plot, analyze, and compute plot level summaries https://github.com/terraref/computing-pipeline/issues/356
