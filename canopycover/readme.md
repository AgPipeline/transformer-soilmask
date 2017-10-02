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
  
  
## Approach 


This extractor processes binary stereo images and generates plot-level percentage canopy cover traits. The core idea for this extractor is a plant-soil segmentation. We apply a threshold to differentiate plant and soil, and do a smoothing after binary processing. At last it returns a plant area ratio within the bounding box.

## Quality Statement 

We believe the tested threshold works well in a normal illumination. Below are some examples of segmentation:
![cc1](https://user-images.githubusercontent.com/20230686/31093445-61dff692-a777-11e7-8c18-f3c2cbfa5882.png)
![cc2](https://user-images.githubusercontent.com/20230686/31093451-6495975c-a777-11e7-9fe9-321e18f05995.png)
![cc3](https://user-images.githubusercontent.com/20230686/31093453-6706da0a-a777-11e7-86c1-0b57b59437fd.png)

At the same time, there are some limitation with the current threshold.

1. Image captured in a low illumination.

![2016-10-07__03-06-00-741](https://user-images.githubusercontent.com/20230686/31093974-183526be-a779-11e7-8f9f-94a295a423f0.jpg)

2. Image captured in a very high illumination.

![2016-09-28__12-19-06-452](https://user-images.githubusercontent.com/20230686/31093901-d89d41bc-a778-11e7-9db9-8b620c3010e2.jpg)

3. In late season, panicle is covering a lot in the image, and leaves is getting yellow.

![2016-11-15__09-45-50-604](https://user-images.githubusercontent.com/20230686/31094142-b006ad50-a779-11e7-9eaa-cfb038a332a0.jpg)

4. Sometimes sensor problem.

![2016-10-10__11-04-18-165](https://user-images.githubusercontent.com/20230686/31094184-e1e4c938-a779-11e7-93eb-c3d3846ffe70.jpg)
