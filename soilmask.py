import pathlib

import numpy as np
import logging
import cv2
import tempfile
from osgeo import gdal, osr

MAX_PIXEL_VAL = 255


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

    sub_img = (g_channel.astype('int') - r_channel.astype(
        'int') - 0) > 0  # normal: -2

    mask = np.zeros_like(b_channel)

    mask[sub_img] = MAX_PIXEL_VAL

    blur = cv2.blur(mask, (kernel_size, kernel_size))
    pix = np.array(blur)
    sub_mask = pix > 128

    mask_1 = np.zeros_like(b_channel)
    mask_1[sub_mask] = MAX_PIXEL_VAL

    return mask_1

def get_epsg(filename):
    """Returns the EPSG of the georeferenced image file
    Args:
        filename(str): path of the file to retrieve the EPSG code from
    Return:
        Returns the found EPSG code, or None if it's not found or an error ocurred
    """
    logger = logging.getLogger(__name__)

    try:
        src = gdal.Open(filename)

        proj = osr.SpatialReference(wkt=src.GetProjection())

        return proj.GetAttrValue('AUTHORITY', 1)
    # pylint: disable=broad-except
    except Exception as ex:
        logger.warn("[get_epsg] Exception caught: %s", str(ex))
    # pylint: enable=broad-except

    return None


def get_image_file_geobounds(filename):
    """Uses gdal functionality to retrieve rectilinear boundaries from the file
    Args:
        filename(str): path of the file to get the boundaries from
    Returns:
        The upper-left and calculated lower-right boundaries of the image in a list upon success.
        The values are returned in following order: min_y, max_y, min_x, max_x. A list of numpy.nan
        is returned if the boundaries can't be determined
    """
    try:
        str_filename = str(filename)
        epsg = get_epsg(str_filename)
        if str(epsg) != "4326":
            _, tmp_name = tempfile.mkstemp()
            src = gdal.Open(str_filename)
            gdal.Warp(tmp_name, src, dstSRS='EPSG:4326')
            str_filename = tmp_name

        src = gdal.Open(str_filename)
        ulx, xres, _, uly, _, yres = src.GetGeoTransform()
        lrx = ulx + (src.RasterXSize * xres)
        lry = uly + (src.RasterYSize * yres)

        min_y = min(uly, lry)
        max_y = max(uly, lry)
        min_x = min(ulx, lrx)
        max_x = max(ulx, lrx)

        return [min_y, max_y, min_x, max_x]
    except Exception as ex:
        logging.info("[image_get_geobounds] Exception caught: %s", str(ex))

    return [np.nan, np.nan, np.nan, np.nan]


def create_geotiff(pixels, gps_bounds, out_path, nodata=-99, asfloat=False, extractor_info=None, system_md=None,
                   extra_metadata=None, compress=True):
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
        gps_bounds[2], # upper-left x
        (gps_bounds[3] - gps_bounds[2])/float(ncols), # W-E pixel resolution
        0, # rotation (0 = North is up)
        gps_bounds[1], # upper-left y
        0, # rotation (0 = North is up)
        -((gps_bounds[1] - gps_bounds[0])/float(nrows)) # N-S pixel resolution
    )

    # Create output GeoTIFF and set coordinates & projection
    if asfloat:
        dtype = gdal.GDT_Float32
    else:
        dtype = gdal.GDT_Byte

    if compress:
        output_raster = gdal.GetDriverByName('GTiff') \
            .Create(str(out_path), ncols, nrows, channels, dtype, ['COMPRESS=LZW'])
    else:
        output_raster = gdal.GetDriverByName('GTiff') \
            .Create(str(out_path), ncols, nrows, channels, dtype)

    output_raster.SetGeoTransform(geotransform)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326) # google mercator
    output_raster.SetProjection( srs.ExportToWkt() )

    if channels == 3:
        # typically 3 channels = RGB channels
        # TODO: Something wonky w/ uint8s --> ending up w/ lots of gaps in data (white pixels)
        output_raster.GetRasterBand(1).WriteArray(pixels[:,:,0].astype('uint8'))
        output_raster.GetRasterBand(1).SetColorInterpretation(gdal.GCI_RedBand)
        output_raster.GetRasterBand(1).FlushCache()
        if nodata:
            output_raster.GetRasterBand(1).SetNoDataValue(nodata)

        output_raster.GetRasterBand(2).WriteArray(pixels[:,:,1].astype('uint8'))
        output_raster.GetRasterBand(2).SetColorInterpretation(gdal.GCI_GreenBand)
        output_raster.GetRasterBand(2).FlushCache()
        if nodata:
            output_raster.GetRasterBand(2).SetNoDataValue(nodata)

        output_raster.GetRasterBand(3).WriteArray(pixels[:,:,2].astype('uint8'))
        output_raster.GetRasterBand(3).SetColorInterpretation(gdal.GCI_BlueBand)
        output_raster.GetRasterBand(3).FlushCache()
        if nodata:
            output_raster.GetRasterBand(3).SetNoDataValue(nodata)

    elif channels > 1:
        # TODO: Something wonky w/ uint8s --> ending up w/ lots of gaps in data (white pixels)
        for chan in range(channels):
            band = chan + 1
            output_raster.GetRasterBand(band).WriteArray(pixels[:,:,chan].astype('uint8'))
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

def load_image(image_path: pathlib.Path) -> np.ndarray:
    img_raw = cv2.imread(str(image_path))
    color_img = cv2.cvtColor(img_raw, cv2.COLOR_BGR2RGB)
    return color_img


def save_mask(output_path: pathlib.Path, bin_mask: np.ndarray):
    np.savez_compressed(output_path, [bin_mask])
