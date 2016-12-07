# Canopy cover extractor
This extractor processes binary stereo images and generates plot-level percentage canopy cover traits for BETYdb.
 
_Input_

  - Evaluation is triggered whenever a file is added to a dataset
  - Following data must be found
    - _left.bin image
    - _right.bin image
    - dataset metadata for the left+right capture dataset; can be attached as Clowder metadata or included as a metadata.json file
    
_Output_

  - The configured BETYdb instance will have canopy coverage traits inserted
  