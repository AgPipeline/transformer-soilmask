"""
# Title:       Improving Image quality from illumination, contrast, noise, and color aspects.
# Detials:     This extractor is designed to improve the RGB image (Gantry or UAS imaging systems) 
               quality in term of visualization from four different aspects: illumination, contrast, noise, and color.
               
               Input : RGB or grayscale image
               Output: Enhanced image
               
# Version:     1.0
# Authors:     Patrick from Remote Sensing Lab at Saint Louis University
# Created:     03/05/2019
"""

#
from pyclowder.utils import CheckMessage
from pyclowder.files import download_metadata, upload_metadata
from pyclowder.datasets import download_metadata as download_ds_metadata
from terrautils.extractors import TerrarefExtractor, build_metadata, upload_to_dataset
from terrautils.metadata import get_extractor_metadata, get_terraref_metadata
from terrautils.formats import create_geotiff
from terrautils.spatial import geojson_to_tuples
#
import numpy as np
from skimage.restoration import denoise_wavelet
from scipy import ndimage
from PIL import Image
#
#
def image_enhance(self, Im):
    # wavelet based denoising
    Im = np.uint8(255*denoise_wavelet(Im, multichannel=True))
    I = np.float32(Im)
    r, c, b = I.shape
    b1,b2,b3 = 2,1,0
    #
    if b > 1:  # grayscale conversion
       I_gray = I[:,:,b1]*0.2989 + I[:,:,b2]*0.5870 + I[:,:,b3]*0.1140
    else:
       I_gray = I 
    #
    # Image normalization
    s = np.float32(I_gray/(np.max(I_gray.flatten())))
    q = 1./(1 + np.exp(-s))
    coef = 0.5  # tunable paramters between 0 - 1
    x = np.float32((np.arctan(coef) + np.arctan(s**q - coef))/(2*np.arctan(coef)))
    #
    # high frequency boosting using laplacian mask
    f = np.array([[ 0, -1, 0], [-1, 4, -1], [0, -1, 0]])/5     
    B = ndimage.convolve(x, f, mode='nearest')
    x = 255*x + B
    #
    #normalize between 0 and 1
    enhanced = 255*(x- x.min())/(x.max()-x.min())
    
    # color restoration
    L = 0.1 # tunable parameters
    t = I_gray
    if b > 1:
       output = np.zeros((r, c, b))
    else:
       output = np.zeros((r, c))    
    #
    if (b > 1):
        I_temp_r = (L*I[:,:,b1]*enhanced)/(t+.001)
        I_temp_g = (L*I[:,:,b2]*enhanced)/(t+.001)
        I_temp_b = (L*I[:,:,b3]*enhanced)/(t+.001)
        #
        red_enh  = I_temp_r
        green_enh= I_temp_g
        blue_enh = I_temp_b
        #
        red_enh_norm = np.float32(np.float32(red_enh - red_enh.min())/(np.float32(red_enh.max() - red_enh.min())))
        enh_red_enh  = np.float32(np.float32(red_enh_norm)*255)
        #
        green_enh_norm=np.float32(np.float32(green_enh-green_enh.min())/(np.float32(green_enh.max() - green_enh.min())))
        enh_green_enh= np.float32(np.float32(green_enh_norm)*255)
        #
        blue_enh_norm=np.float32(np.float32(blue_enh - blue_enh.min())/(np.float32(blue_enh.max() - blue_enh.min())))
        enh_blue_enh= np.float32(np.float32(blue_enh_norm)*255)
        
        output[:,:,b1] = enh_red_enh
        output[:,:,b2] = enh_green_enh
        output[:,:,b3] = enh_blue_enh
    else:
        output = enhanced
    
    #  Enhanced image 
    enhanced_image = np.uint8(output)
    return enhanced_image


def getEnhancedImage(self, imgfile):
    img = Image.open(imgfile)
    img = np.array(img)
    EnImage = image_enhance(img)
    return EnImage


class RGB_Enhance(TerrarefExtractor):
    def __init__(self):
        super(RGB_Enhance, self).__init__()

        # parse command line and load default logging configuration
        self.setup(sensor='rgb_geotiff')

    def check_message(self, connector, host, secret_key, resource, parameters):
        if "rulechecked" in parameters and parameters["rulechecked"]:
            return CheckMessage.download
        self.start_check(resource)

        if resource['name'].endswith('_left.tif') or resource['name'].endswith('_right.tif'):
            # Check metadata to verify we have what we need
            md = download_metadata(connector, host, secret_key, resource['id'])
            if get_extractor_metadata(md, self.extractor_info['name']) and not self.overwrite:
                self.log_skip(resource, "metadata indicates it was already processed")
                return CheckMessage.ignore
            return CheckMessage.download
        else:
            self.log_skip(resource, "not left/right geotiff")
            return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message(resource)

        f = resource['local_paths'][0]

        self.log_info(resource, "determining image quality")
        EI = getEnhancedImage(f)  # Enhanced Image (EI)

        self.log_info(resource, "creating output image")
        md = download_ds_metadata(connector,host, secret_key, resource['parent']['id'])
        terramd = get_terraref_metadata(md)
        if "left" in f:
            bounds = geojson_to_tuples(terramd['spatial_metadata']['left']['bounding_box'])
        else:
            bounds = geojson_to_tuples(terramd['spatial_metadata']['right']['bounding_box'])
        output = f.replace(".tif", "_nrmac.tif")
        create_geotiff(np.array([[EI,EI],[EI,EI]]), bounds, output)
        upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, resource['parent']['id'], output)

        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        ext_meta = build_metadata(host, self.extractor_info, resource['id'], {
            "quality_score": EI
        }, 'file')
        self.log_info(resource, "uploading extractor metadata")
        upload_metadata(connector, host, secret_key, resource['id'], ext_meta)

        self.end_message(resource)


if __name__ == "__main__":
    extractor = RGB_Enhance()
    extractor.start()