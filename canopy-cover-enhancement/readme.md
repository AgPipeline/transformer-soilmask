RGB image enhancement by GAN

rgb plant mask

#############################################

## Title: Improving Image quality from illumination, contrast, noise, and color aspects.

### Description
This extractor is designed to improve the RGB image (Gantry or UAS imaging systems) quality in term of visualization from four different aspects: illumination, contrast, noise, and color.

_Input_ : RGB or grayscale image

_Output_ : Enhanced image

### Suggestion
This extractor can be combined with RGB image quality extractor. Whenever the image quality score is lower the expected value, this image enhancement algorithm can be triggered and apply to the raw input image.

### Background
Due to the limitations of UAS (unmanned aerial system) or other imaging devices, image enhancement has become a necessary process for improving the visual appearance images. Although a great amount of effort has been focused on improving image quality from different aspects, the major obstacles are from computational or operational efficiency and complexity, such as manually adjusting the associated camera settings or algorithmic parameters that account for various image luminance or signal-to-noise ratio. To overcome these drawbacks, we propose a new adaptive yet highly efficient image enhancement method for enhancing the quality of digital color images in terms of illumination, contrast, color and signal-to-noise ratio. The proposed method is derived from a trigonometric transformation, high frequency boosting functions, wavelet transform, and a color restoration process whose characteristics adaptively change with respect to the variation of the image luminance, contrast, color and noise level.
