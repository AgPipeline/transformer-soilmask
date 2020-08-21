#!/usr/bin/env python3
"""Soil masking Transformer
"""

import logging
import os
import numpy as np
import sys
from agpypeline import entrypoint, algorithm, geoimage
from agpypeline.environment import Environment
import cv2

from osgeo import gdal
# from PIL import Image  Used by code that's getting deprecated
from skimage import morphology

from configuration import ConfigurationSoilmask

SATURATE_THRESHOLD = 245
MAX_PIXEL_VAL = 255
SMALL_AREA_THRESHOLD = 200


class __internal__:
    """Class for functions intended for internal use only for this file
    """
    def __init__(self):
        """Performs initialization of class instance
        """

    @staticmethod
    def prepare_metadata_for_geotiff(transformer_info: dict = None) -> dict:
        """Create geotiff-embedable metadata from extractor_info and other metadata pieces.
        Arguments:
            transformer_info: details about the transformer
        Return:
            A dict containing information to save with an image
        """
        extra_metadata = {}

        if transformer_info:
            extra_metadata["transformer_name"] = str(transformer_info.get("name", ""))
            extra_metadata["transformer_version"] = str(transformer_info.get("version", ""))
            extra_metadata["transformer_author"] = str(transformer_info.get("author", ""))
            extra_metadata["transformer_description"] = str(transformer_info.get("description", ""))
            if "repository" in transformer_info and transformer_info["repository"] and \
                    "repUrl" in transformer_info["repository"]:
                extra_metadata["transformer_repo"] = str(transformer_info["repository"]["repUrl"])
            else:
                extra_metadata["transformer_repo"] = ""

        return extra_metadata

    @staticmethod
    def gen_plant_mask(color_img: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        """Generates an image with plants masked in.
        Arguments:
            color_img: RGB image to mask
            kernel_size: masking kernel size
        Return:
            An RGB image with plants masked in
        """
        r_channel = color_img[:, :, 2]
        g_channel = color_img[:, :, 1]
        b_channel = color_img[:, :, 0]

        sub_img = (g_channel.astype('int') - r_channel.astype('int') - 0) > 0  # normal: -2

        mask = np.zeros_like(b_channel)

        mask[sub_img] = MAX_PIXEL_VAL

        blur = cv2.blur(mask, (kernel_size, kernel_size))
        pix = np.array(blur)
        sub_mask = pix > 128

        mask_1 = np.zeros_like(b_channel)
        mask_1[sub_mask] = MAX_PIXEL_VAL

        return mask_1

    @staticmethod
    def remove_small_area_mask(mask_img: np.ndarray, min_area_size: int) -> np.ndarray:
        """Removes small anomalies in the mask
        Arguments:
            mask_img: the mask image to remove anomalies from
            min_area_size: the size of anomalies to look for
        Return:
            A new mask image with the anomalies removed
        """
        mask_array = mask_img > 0
        rel_array = morphology.remove_small_objects(mask_array, min_area_size)

        rel_img = np.zeros_like(mask_img)
        rel_img[rel_array] = MAX_PIXEL_VAL

        return rel_img

    @staticmethod
    def remove_small_holes_mask(mask_image: np.ndarray, max_hole_size: int) -> np.ndarray:
        """Removes small holes from the mask image
        Arguments:
            mask_image: the mask image to remove holes from
            max_hole_size: the maximum size of holes to remove
        Return:
            A new mask image with the holes removed
        """
        mask_array = mask_image > 0
        rel_array = morphology.remove_small_holes(mask_array, max_hole_size)
        rel_img = np.zeros_like(mask_image)
        rel_img[rel_array] = MAX_PIXEL_VAL

        return rel_img

    @staticmethod
    def saturated_pixel_classification(gray_img: np.ndarray, base_mask: np.ndarray, saturated_mask: np.ndarray,
                                       dilate_size: int = 0) -> np.ndarray:
        """Returns an image with pixes classified for masking
        Arguments:
        Returns:
            A mask image with the pixels classified
        """
        # add saturated area into basic mask
        saturated_mask = morphology.binary_dilation(saturated_mask, morphology.diamond(dilate_size))

        rel_img = np.zeros_like(gray_img)
        rel_img[saturated_mask] = MAX_PIXEL_VAL

        label_img, num = morphology.label(rel_img, connectivity=2, return_num=True)

        rel_mask = base_mask

        for idx in range(1, num):
            match = (label_img == idx)

            if np.sum(match) > 100000:  # if the area is too large, do not add it into basic mask
                continue

            if not (match & base_mask).any():
                continue

            rel_mask = rel_mask | match

        return rel_mask

    @staticmethod
    def over_saturation_process(rgb_image: np.ndarray, init_mask: np.ndarray, threshold: int = SATURATE_THRESHOLD) -> np.ndarray:
        """Removes over saturated areas from an image
        Arguments:
            rgb_image: the image to process
            init_mask:
            threshold: The saturation threshold value
        Return:
            A new image with over saturated pixels removed
        """
        # connected component analysis for over saturation pixels
        gray_img = cv2.cvtColor(rgb_image, cv2.COLOR_BGR2GRAY)

        mask_over = gray_img > threshold

        mask_0 = gray_img < threshold

        src_mask_array = init_mask > 0

        mask_1 = src_mask_array & mask_0

        mask_1 = morphology.remove_small_objects(mask_1, SMALL_AREA_THRESHOLD)

        mask_over = morphology.remove_small_objects(mask_over, SMALL_AREA_THRESHOLD)

        rel_mask = __internal__.saturated_pixel_classification(gray_img, mask_1, mask_over, 1)
        rel_img = np.zeros_like(gray_img)
        rel_img[rel_mask] = MAX_PIXEL_VAL

        return rel_img

    @staticmethod
    def gen_saturated_mask(img: np.ndarray, kernel_size: int) -> np.ndarray:
        """Generates a mask of over saturated pixels
        Arguments:
            img: the image to generate the mask from
            kernel_size: the size of masking kernel
        Returns:
            The image mask of over saturated pixels
        """
        bin_mask = __internal__.gen_plant_mask(img, kernel_size)
        bin_mask = __internal__.remove_small_area_mask(bin_mask,
                                                       500)  # 500 is a parameter for number of pixels to be removed as small area
        bin_mask = __internal__.remove_small_holes_mask(bin_mask,
                                                        300)  # 300 is a parameter for number of pixels to be filled as small holes

        bin_mask = __internal__.over_saturation_process(img, bin_mask, SATURATE_THRESHOLD)

        bin_mask = __internal__.remove_small_holes_mask(bin_mask, 4000)

        return bin_mask

    @staticmethod
    def gen_mask(img: np.ndarray, kernel_size: int) -> np.ndarray:
        """Generated the mask for plants
        Arguments:
            img: the image used to mask in plants
            kernel_size: the size of the image processing kernel
        Return:
            A new image mask
        """
        bin_mask = __internal__.gen_plant_mask(img, kernel_size)
        bin_mask = __internal__.remove_small_area_mask(bin_mask, SMALL_AREA_THRESHOLD)
        bin_mask = __internal__.remove_small_holes_mask(bin_mask,
                                                        3000)  # 3000 is a parameter for number of pixels to be filled as small holes

        return bin_mask

    @staticmethod
    def gen_rgb_mask(img: np.ndarray, bin_mask: np.ndarray) -> np.ndarray:
        """Applies the mask to the image
        Arguments:
            img: the source image to mask
            bin_mask: the mask to apply to the image
        Return:
            A new image that had the mask applied
        """
        rgb_mask = cv2.bitwise_and(img, img, mask=bin_mask)

        return rgb_mask

    @staticmethod
    def check_saturation(img: np.ndarray) -> list:
        """Checks the saturation of an image
        Arguments:
            img: the image to check
        Return:
            A list containing the over threshold rate and the under threshold rate
        """
        # check how many percent of pix close to 255 or 0
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        over_threshold = gray_img > SATURATE_THRESHOLD
        under_threshold = gray_img < 20  # 20 is a threshold to classify low pixel value

        over_rate = float(np.sum(over_threshold)) / float(gray_img.size)
        low_rate = float(np.sum(under_threshold)) / float(gray_img.size)

        return [over_rate, low_rate]

    @staticmethod
    def get_maskfilename(filename: str) -> str:
        """Returns the name of the file to use as a mask. Any path information
           in the filename parameter is not returned.
        Arguments:
            filename: the name of the file to convert to a mask name
        Return:
            The name of the mask file
        """
        base, ext = os.path.splitext(os.path.basename(filename))

        return base + "_mask" + ext


def gen_cc_enhanced(input_path: str, kernel_size: int = 3) -> tuple:
    """Generates an image mask keeping plants
    Arguments:
        input_path: the path to the input image
        kernel_size: the image kernel size for processing
    Return:
        A list containing the percent of unmasked pixels and the masked image
    """
    # abandon low quality images, mask enhanced
    img = np.rollaxis(gdal.Open(input_path).ReadAsArray().astype(np.uint8), 0, 3)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # calculate image scores
    # pylint: disable=unused-variable
    over_rate, low_rate = __internal__.check_saturation(img)

    # if low score, return None
    # low_rate is percentage of low value pixels(lower than 20) in the grayscale image, if low_rate > 0.1, return
    # aveValue is average pixel value of grayscale image, if aveValue lower than 30 or higher than 195, return
    # quality_score is a score from Multiscale Autocorrelation (MAC), if quality_score lower than 13, return

    # aveValue = check_brightness(img)
    # quality_score = get_image_quality(input_path)
    # if low_rate > 0.1 or aveValue < 30 or aveValue > 195 or quality_score < 13:
    #    return None, None, None

    # saturated image process
    # over_rate is percentage of high value pixels(higher than SATURATE_THRESHOLD) in the grayscale image, if
    # over_rate > 0.15, try to fix it use gen_saturated_mask()
    if over_rate > 0.15:
        bin_mask = __internal__.gen_saturated_mask(img, kernel_size)
    else:  # normal image process
        bin_mask = __internal__.gen_mask(img, kernel_size)

    count = np.count_nonzero(bin_mask)
    ratio = count / float(bin_mask.size)

    rgb_mask = __internal__.gen_rgb_mask(img, bin_mask)

    return ratio, rgb_mask


class SoilMask(algorithm.Algorithm):
    """Masks soil from an image"""

    @property
    def supported_file_ext(self) -> tuple:
        """Returns a tuple of supported file extensions in lowercase (with the preceeding dot: eg '.tif')"""
        return '.tiff', '.tif'

    def check_continue(self, environment: Environment, check_md: dict, transformer_md: list,
                       full_md: list) -> tuple:
        """Checks if conditions are right for continuing processing
        Arguments:
            environment: instance of environment class
            check_md: the metadata for this request
            transformer_md: the metadata associated with this transformer
            full_md: the full set of original metadata
        Return:
            Returns a tuple containing the return code for continuing or not, and
            an error message if there's an error
        """
        # pylint: disable=unused-argument
        result = {'code': -1002, 'message': "No TIFF files were specified for processing"}

        # Ensure we have a TIFF file
        if check_md and 'list_files' in check_md:
            files = check_md['list_files']()
            try:
                for one_file in files:
                    ext = os.path.splitext(one_file)[1].lower()
                    if ext in self.supported_file_ext:
                        result['code'] = 0
                        break
            except Exception as ex:
                result['code'] = -1
                result['error'] = "Exception caught processing file list: %s" % str(ex)
        else:
            result['code'] = -1
            result['error'] = "Check metadata parameter is not configured to provide a list of files"

        return (result['code'], result['error']) if 'error' in result else (result['code'])

    def perform_process(self, environment: Environment, check_md: dict, transformer_md: dict,
                        full_md: list) -> dict:
        """Performs the processing of the data
        Arguments:
            environment: instance of environment class
            check_md: the metadata for this request
            transformer_md: the metadata associated with this transformer
            full_md: the full set of original metadata
        Return:
            Returns a dictionary with the results of processing
        """
        # pylint: disable=unused-argument
        result = {}
        file_md = []

        # Loop through the files
        try:
            for one_file in check_md['list_files']():
                # Check file by type
                ext = os.path.splitext(one_file)[1].lower()
                if ext not in self.supported_file_ext:
                    continue
                if not os.path.exists(one_file):
                    logging.warning("Unable to access file '%s'", one_file)
                    continue

                # Get the image's EPSG code
                epsg = geoimage.get_epsg(one_file)
                if epsg is None:
                    logging.debug("Skipping image that is not georeferenced: '%s'", one_file)
                    continue

                # Get the bounds of the image to see if we can process it.
                bounds = geoimage.image_get_geobounds(one_file)

                if bounds is None:
                    logging.warning("Unable to get bounds of georeferenced image: '%s'",
                                    os.path.basename(one_file))
                    continue

                # Get the mask name using the original name as reference
                rgb_mask_tif = os.path.join(check_md['working_folder'], __internal__.get_maskfilename(one_file))

                # Create the mask file
                logging.debug("Creating mask file '%s'", rgb_mask_tif)
                mask_ratio, mask_rgb = gen_cc_enhanced(one_file)

                # Bands must be reordered to avoid swapping R and B
                mask_rgb = cv2.cvtColor(mask_rgb, cv2.COLOR_BGR2RGB)

                transformer_info = environment.generate_transformer_md()

                image_md = __internal__.prepare_metadata_for_geotiff(transformer_info)
                geoimage.create_geotiff(mask_rgb, bounds, rgb_mask_tif, epsg, None, False, image_md, compress=True)

                transformer_md = {
                    'name': transformer_info['name'],
                    'version': transformer_info['version'],
                    'ratio': mask_ratio
                }

                new_file_md = {'path': rgb_mask_tif,
                               'key': ConfigurationSoilmask.transformer_sensor,
                               'metadata': {
                                   'data': transformer_md
                               }
                              }
                file_md.append(new_file_md)

            result['code'] = 0
            result['file'] = file_md

        except Exception as ex:
            result['code'] = -1001
            result['error'] = "Exception caught masking files: %s" % str(ex)

        return result


if __name__ == "__main__":
    CONFIGURATION = ConfigurationSoilmask()
    entrypoint.entrypoint(CONFIGURATION, SoilMask())
    sys.exit(0)
