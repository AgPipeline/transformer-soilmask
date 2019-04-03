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

import os
import numpy as np
from skimage.restoration import denoise_wavelet
from scipy import ndimage
from PIL import Image

from pyclowder.utils import CheckMessage
from pyclowder.datasets import remove_metadata, download_metadata, upload_metadata
from terrautils.extractors import TerrarefExtractor, build_metadata, upload_to_dataset, is_latest_file, \
    contains_required_files, file_exists, load_json_file, check_file_in_dataset
from terrautils.metadata import get_extractor_metadata, get_terraref_metadata
from terrautils.formats import create_geotiff
from terrautils.spatial import geojson_to_tuples


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
        self.setup(sensor='rgb_enhanced')

    def check_message(self, connector, host, secret_key, resource, parameters):
        if "rulechecked" in parameters and parameters["rulechecked"]:
            return CheckMessage.download

        self.start_check(resource)

        if not is_latest_file(resource):
            self.log_skip(resource, "not latest file")
            return CheckMessage.ignore

        # Check for a left and right BIN file - skip if not found
        if not contains_required_files(resource, ['_left.tif', '_right.tif']):
            self.log_skip(resource, "missing required files")
            return CheckMessage.ignore

        # Check metadata to verify we have what we need
        md = download_metadata(connector, host, secret_key, resource['id'])
        if get_terraref_metadata(md):
            if get_extractor_metadata(md, self.extractor_info['name'], self.extractor_info['version']):
                # Make sure outputs properly exist
                timestamp = resource['dataset_info']['name'].split(" - ")[1]
                left_enh_tiff = self.sensors.create_sensor_path(timestamp, opts=['left'])
                right_enh_tiff = self.sensors.create_sensor_path(timestamp, opts=['right'])
                if file_exists(left_enh_tiff) and file_exists(right_enh_tiff):
                    if contains_required_files(resource, [os.path.basename(left_enh_tiff), os.path.basename(right_enh_tiff)]):
                        self.log_skip(resource, "metadata v%s and outputs already exist" % self.extractor_info['version'])
                        return CheckMessage.ignore
                    else:
                        self.log_info(resource, "output files exist but not yet uploaded")
            # Have TERRA-REF metadata, but not any from this extractor
            return CheckMessage.download
        else:
            self.log_error(resource, "no terraref metadata found")
            return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message(resource)

        # Get left/right files and metadata
        img_left, img_right, metadata = None, None, None
        for fname in resource['local_paths']:
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = load_json_file(fname)
                terra_md_full = get_terraref_metadata(all_dsmd, 'stereoTop')
            elif fname.endswith('_left.tif'):
                img_left = fname
            elif fname.endswith('_right.tif'):
                img_right = fname
        if None in [img_left, img_right, terra_md_full]:
            raise ValueError("could not locate all files & metadata in processing")

        timestamp = resource['dataset_info']['name'].split(" - ")[1]
        target_dsid = resource['id']

        left_rgb_enh_tiff = self.sensors.create_sensor_path(timestamp, opts=['left'])
        right_rgb_enh_tiff = self.sensors.create_sensor_path(timestamp, opts=['right'])
        uploaded_file_ids = []

        left_bounds = geojson_to_tuples(terra_md_full['spatial_metadata']['left']['bounding_box'])
        right_bounds = geojson_to_tuples(terra_md_full['spatial_metadata']['right']['bounding_box'])


        if not file_exists(left_rgb_enh_tiff) or self.overwrite:
            self.log_info(resource, "creating %s" % left_rgb_enh_tiff)
            EI = getEnhancedImage(img_left)
            create_geotiff(np.array([[EI,EI],[EI,EI]]), left_bounds, left_rgb_enh_tiff)
            self.created += 1
            self.bytes += os.path.getsize(left_rgb_enh_tiff)

        found_in_dest = check_file_in_dataset(connector, host, secret_key, target_dsid, left_rgb_enh_tiff,
                                              remove=self.overwrite)
        if not found_in_dest:
            self.log_info(resource, "uploading %s" % left_rgb_enh_tiff)
            fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid,
                                       left_rgb_enh_tiff)
            uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)


        if not file_exists(right_rgb_enh_tiff) or self.overwrite:
            self.log_info(resource, "creating %s" % right_rgb_enh_tiff)
            EI = getEnhancedImage(img_left)
            create_geotiff(np.array([[EI,EI],[EI,EI]]), right_bounds, right_rgb_enh_tiff)
            self.created += 1
            self.bytes += os.path.getsize(right_rgb_enh_tiff)

        found_in_dest = check_file_in_dataset(connector, host, secret_key, target_dsid, right_rgb_enh_tiff,
                                              remove=self.overwrite)
        if not found_in_dest:
            self.log_info(resource, "uploading %s" % right_rgb_enh_tiff)
            fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid,
                                       right_rgb_enh_tiff)
            uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)


        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        ext_meta = build_metadata(host, self.extractor_info, target_dsid, {
            "files_created": uploaded_file_ids
        }, 'dataset')
        self.log_info(resource, "uploading extractor metadata")
        remove_metadata(connector, host, secret_key, target_dsid, self.extractor_info['name'])
        upload_metadata(connector, host, secret_key, target_dsid, ext_meta)

        self.end_message(resource)


if __name__ == "__main__":
    extractor = RGB_Enhance()
    extractor.start()