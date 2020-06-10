"""Testing instance of transformer
"""

import logging
import os
import tempfile
import numpy as np
import cv2

from osgeo import gdal, osr
# from PIL import Image  Used by code that's getting deprecated
from skimage import morphology

import configuration
import transformer_class

SATURATE_THRESHOLD = 245
MAX_PIXEL_VAL = 255
SMALL_AREA_THRESHOLD = 200


class __internal__():
    """Class for functions intended for internal use only for this file
    """
    def __init__(self):
        """Performs initialization of class instance
        """

    @staticmethod
    def prepare_metadata_for_geotiff(extractor_info=None, terra_md=None):
        """Create geotiff-embedded metadata from extractor_info and terraref metadata pieces.

            Keyword arguments:
            extractor_info -- details about extractor if applicable
            system_md -- cleaned TERRA-REF metadata
        """
        extra_metadata = {}

        if (terra_md != None):
            extra_metadata["datetime"] = str(terra_md["gantry_variable_metadata"]["datetime"])
            extra_metadata["sensor_id"] = str(terra_md["sensor_fixed_metadata"]["sensor_id"])
            extra_metadata["sensor_url"] = str(terra_md["sensor_fixed_metadata"]["url"])
            experiment_names = []
            for e in terra_md["experiment_metadata"]:
                experiment_names.append(e["name"])
            terra_md["experiment_name"] = ", ".join(experiment_names)

        if (extractor_info != None):
            extra_metadata["extractor_name"] = str(extractor_info.get("name", ""))
            extra_metadata["extractor_version"] = str(extractor_info.get("version", ""))
            extra_metadata["extractor_author"] = str(extractor_info.get("author", ""))
            extra_metadata["extractor_description"] = str(extractor_info.get("description", ""))
            if "repository" in extractor_info and "repUrl" in extractor_info["repository"]:
                extra_metadata["extractor_repo"] = str(extractor_info["repository"]["repUrl"])
            else:
                extra_metadata["extractor_repo"] = ""

        return extra_metadata

    @staticmethod
    def create_geotiff(pixels, gps_bounds, out_path, nodata=-99, asfloat=False, extractor_info=None, system_md=None,
                       extra_metadata=None, compress=False):
        """Generate output GeoTIFF file given a numpy pixel array and GPS boundary.

            Keyword arguments:
            pixels -- numpy array of pixel values.
                        if 2-dimensional array, a single-band GeoTIFF will be created.
                        if 3-dimensional array, a band will be created for each Z dimension.
            gps_bounds -- tuple of GeoTIFF coordinates as ( lat (y) min, lat (y) max,
                                                            long (x) min, long (x) max)
            out_path -- path to GeoTIFF to be created
            nodata -- NoDataValue to be assigned to raster bands; set to None to ignore
            float -- whether to use GDT_Float32 data type instead of GDT_Byte (e.g. for decimal numbers)
            extractor_info -- details about extractor if applicable
            system_md -- cleaned TERRA-REF metadata
            extra_metadata -- any metadata to be embedded in geotiff; supersedes extractor_info and system_md
        """
        dimensions = np.shape(pixels)
        if len(dimensions) == 2:
            nrows, ncols = dimensions
            channels = 1
        else:
            nrows, ncols, channels = dimensions

        geotransform = (
            gps_bounds[2],  # upper-left x
            (gps_bounds[3] - gps_bounds[2]) / float(ncols),  # W-E pixel resolution
            0,  # rotation (0 = North is up)
            gps_bounds[1],  # upper-left y
            0,  # rotation (0 = North is up)
            -((gps_bounds[1] - gps_bounds[0]) / float(nrows))  # N-S pixel resolution
        )

        # Create output GeoTIFF and set coordinates & projection
        if asfloat:
            dtype = gdal.GDT_Float32
        else:
            dtype = gdal.GDT_Byte

        if compress:
            output_raster = gdal.GetDriverByName('GTiff') \
                .Create(out_path, ncols, nrows, channels, dtype, ['COMPRESS=LZW'])
        else:
            output_raster = gdal.GetDriverByName('GTiff') \
                .Create(out_path, ncols, nrows, channels, dtype)

        output_raster.SetGeoTransform(geotransform)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)  # google mercator
        output_raster.SetProjection(srs.ExportToWkt())

        if not extra_metadata:
            extra_metadata = __internal__.prepare_metadata_for_geotiff(extractor_info, system_md)

        output_raster.SetMetadata(extra_metadata)

        if channels == 3:
            # typically 3 channels = RGB channels
            # TODO: Something wonky w/ uint8s --> ending up w/ lots of gaps in data (white pixels)
            output_raster.GetRasterBand(1).WriteArray(pixels[:, :, 0].astype('uint8'))
            output_raster.GetRasterBand(1).SetColorInterpretation(gdal.GCI_RedBand)
            output_raster.GetRasterBand(1).FlushCache()
            if nodata:
                output_raster.GetRasterBand(1).SetNoDataValue(nodata)

            output_raster.GetRasterBand(2).WriteArray(pixels[:, :, 1].astype('uint8'))
            output_raster.GetRasterBand(2).SetColorInterpretation(gdal.GCI_GreenBand)
            output_raster.GetRasterBand(2).FlushCache()
            if nodata:
                output_raster.GetRasterBand(2).SetNoDataValue(nodata)

            output_raster.GetRasterBand(3).WriteArray(pixels[:, :, 2].astype('uint8'))
            output_raster.GetRasterBand(3).SetColorInterpretation(gdal.GCI_BlueBand)
            output_raster.GetRasterBand(3).FlushCache()
            if nodata:
                output_raster.GetRasterBand(3).SetNoDataValue(nodata)

        elif channels > 1:
            # TODO: Something wonky w/ uint8s --> ending up w/ lots of gaps in data (white pixels)
            for chan in range(channels):
                band = chan + 1
                output_raster.GetRasterBand(band).WriteArray(pixels[:, :, chan].astype('uint8'))
                output_raster.GetRasterBand(band).FlushCache()
                if nodata:
                    output_raster.GetRasterBand(band).SetNoDataValue(nodata)
        else:
            # single channel image, e.g. temperature
            output_raster.GetRasterBand(1).WriteArray(pixels)
            output_raster.GetRasterBand(1).FlushCache()
            if nodata:
                output_raster.GetRasterBand(1).SetNoDataValue(nodata)

        output_raster = None

#    @staticmethod
#    def get_image_quality(imgfile: str) -> np.ndarray:
#        """Computes and returns the image score for the image file
#        Arguments:
#            imgfile: the name of the file to compute the score for
#        Returns:
#            The score for the image
#        """
#        img = Image.open(imgfile)
#        img = np.array(img)
#
#        nrmac = __internal__.MAC(img, img, img)
#
#        return nrmac

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

#    @staticmethod
#    def rgb2gray(rgb: np.ndarray) -> np.ndarray:
#        """Converts RGB image to grey scale
#        Arguments:
#            rgb: the image to convert
#        Return:
#            The greyscale image
#        """
#        r_channel, g_channel, b_channel = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
#        gray = 0.2989 * r_channel + 0.5870 * g_channel + 0.1140 * b_channel
#        return gray

#    @staticmethod
#    def MAC(im1: np.ndarray, im2: np.ndarray, im: np.ndarray) -> np.ndarray:    # pylint: disable=invalid-name
#        """Calculates an image score of Multiscale Autocorrelation (MAC)
#        Arguments:
#        Return:
#            Returns the scored image
#        """
#        h_dim, _, c_dim = im1.shape
#        if c_dim > 1:
#            im = np.matrix.round(__internal__.rgb2gray(im))
#            im1 = np.matrix.round(__internal__.rgb2gray(im1))
#            im2 = np.matrix.round(__internal__.rgb2gray(im2))
#        # multiscale parameters
#        scales = np.array([2, 3, 5])
#        fm_arr = np.zeros(len(scales))
#        for idx, _ in enumerate(scales):
#            im1[0: h_dim - 1, :] = im[1:h_dim, :]
#            im2[0: h_dim - scales[idx], :] = im[scales[idx]:h_dim, :]
#            dif = im * (im1 - im2)
#            fm_arr[idx] = np.mean(dif)
#        nrmac = np.mean(fm_arr)
#        return nrmac

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

        return over_rate, low_rate

#    @staticmethod
#    def check_brightness(img: np.ndarray) -> float:
#        """Generates average pixel value from grayscale image
#        Arguments:
#            img: the source image
#        Returns:
#            The average pixel value of the image
#        """
#        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#
#        avg_value = np.average(gray_img)
#
#        return avg_value

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
        A list contianing the percent of unmasked pixels and the masked image
    """
    # abandon low quality images, mask enhanced
    # TODO: cv2 has problems with some RGB geotiffs...
    # img = cv2.imread(input_path)
    img = np.rollaxis(gdal.Open(input_path).ReadAsArray().astype(np.uint8), 0, 3)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # calculate image scores
    # pylint: disable=unused-variable
    over_rate, low_rate = __internal__.check_saturation(img)

    # TODO: disabling this check for now because it's crashing extractor - generate mask regardless
    # if low score, return None
    # low_rate is percentage of low value pixels(lower than 20) in the grayscale image, if low_rate > 0.1, return
    # aveValue is average pixel value of grayscale image, if aveValue lower than 30 or higher than 195, return
    # quality_score is a score from Multiscale Autocorrelation (MAC), if quality_score lower than 13, return

    # saveValue = check_brightness(img)
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


def check_continue(transformer: transformer_class.Transformer, check_md: dict, transformer_md: list,
                   full_md: list) -> tuple:
    """Checks if conditions are right for continuing processing
    Arguments:
        transformer: instance of transformer class
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
                if ext in ('.tiff', '.tif'):
                    result['code'] = 0
                    break
        except Exception as ex:
            result['code'] = -1
            result['error'] = "Exception caught processing file list: %s" % str(ex)
    else:
        result['code'] = -1
        result['error'] = "Check metadata parameter is not configured to provide a list of files"

    return (result['code'], result['error']) if 'error' in result else (result['code'])


def perform_process(transformer: transformer_class.Transformer, check_md: dict, transformer_md: list,
                    full_md: list) -> dict:
    """Performs the processing of the data
    Arguments:
        transformer: instance of transformer class'
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
            if ext not in ('.tiff', '.tif'):
                continue
            if not os.path.exists(one_file):
                logging.warning("Unable to access file '%s'", one_file)
                continue
            mask_source = one_file

            # Get the image's EPSG code
            epsg = transformer.get_image_file_epsg(mask_source)
            if epsg is None:
                logging.debug("Skipping image that is not georeferenced: '%s'", mask_source)
                continue

            # Check that it's geo referenced and transform it if it'sin the wrong coordinate system
            if epsg != transformer.default_epsg:
                logging.info("Reprojecting image from EPSG %s to default EPSG %s", str(epsg),
                             str(transformer.default_epsg))
                _, tmp_name = tempfile.mkstemp(dir=check_md['working_folder'])
                src = gdal.Open(mask_source)
                gdal.Warp(tmp_name, src, dstSRS='EPSG:'+str(transformer.default_epsg))
                mask_source = tmp_name

            # Get the bounds of the image to see if we can process it.
            bounds = transformer.get_image_file_geobounds(mask_source)

            if bounds is None:
                logging.warning("Unable to get bounds of georeferenced image: '%s'",
                                os.path.basename(one_file))
                if mask_source != one_file:
                    os.remove(mask_source)
                continue

            # Get the mask name using the original name as reference
            rgb_mask_tif = os.path.join(check_md['working_folder'], __internal__.get_maskfilename(one_file))

            # Create the mask file
            logging.debug("Creating mask file '%s'", rgb_mask_tif)
            mask_ratio, mask_rgb = gen_cc_enhanced(mask_source)

            # Bands must be reordered to avoid swapping R and B
            mask_rgb = cv2.cvtColor(mask_rgb, cv2.COLOR_BGR2RGB)

            transformer_info = transformer.generate_transformer_md()

            __internal__.create_geotiff(mask_rgb, bounds, rgb_mask_tif, None, False,
                              transformer_info, check_md['context_md'], compress=True)

            # Remove any temporary file
            if mask_source != one_file:
                os.remove(mask_source)

            transformer_md = {
                'name': transformer_info['name'],
                'version': transformer_info['version'],
                'ratio': mask_ratio
            }

            new_file_md = {'path': rgb_mask_tif,
                           'key': configuration.TRANSFORMER_SENSOR,
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
