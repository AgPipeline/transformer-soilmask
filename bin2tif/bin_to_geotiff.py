#!/usr/bin/env python

'''
Created on May 3, 2016
Author: Joshua Little, Zongyang Li
This script takes in a folder that contains the metadata associated with a particular
stereo pair (*_metadata.json) and the binary stereo images (*_left.bin and *_right.bin),
and outputs demosaiced .jpg files and .tif files.
----------------------------------------------------------------------------------------
Usage:
python input_folder output_folder
where
input_folder        is the folder containing the metadata and binary stereo image inputs
output_folder     is the folder where the output .jpg files and .tif files will be saved
'''

import sys, os.path, json
from glob import glob
from os.path import join
import numpy as np
from scipy.ndimage.filters import convolve
from PIL import Image
from math import cos, pi
from osgeo import gdal, osr
import utm

ZERO_ZERO = (33.07451869,-111.97477775) # (latitude, longitude) of SE corner (positions are + in NW direction); I think this is EPSG4326 (wgs84)
# NOTE: This STEREO_OFFSET is an experimentally determined value.
STEREO_OFFSET = .17 # distance from center_position to each of the stereo cameras (left = +, right = -)

## PARAMS FROM 5/8
HEIGHT_MAGIC_NUMBER = 1.64 # this is the value we have to add to our Z position to get the images in a column to line up.

# Test by Baker
FOV_MAGIC_NUMBER = 0.1552 
FOV_IN_2_METER_PARAM = 0.837 # since we don't have a true value of field of view in 2 meters, we use this parameter(meter) to estimate fov in Y-

# PARAMS FROM 5/25
#HEIGHT_MAGIC_NUMBER = 1.3 # this is the value we have to add to our Z position to get the images in a column to line up.

# Scanalyzer -> MAC formular @ https://terraref.gitbooks.io/terraref-documentation/content/user/geospatial-information.html
# Mx = ax + bx * Gx + cx * Gy
# My = ay + by * Gx + cy * Gy
SE_latlon = (33.07451869,-111.97477775)
ay = 3659974.971; by = 1.0002; cy = 0.0078;
ax = 409012.2032; bx = 0.009; cx = - 0.9986;
lon_shift = 0.000020308287
lat_shift = 0.000015258894
SE_utm = utm.from_latlon(SE_latlon[0], SE_latlon[1])

def main(in_dir, out_dir, tif_list_file, bounds):
    if not os.path.isdir(in_dir):
        fail('Could not find input directory: ' + in_dir)
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    metas, ims_left, ims_right = find_input_files(in_dir)

    for meta, im_left, im_right in zip(metas, ims_left, ims_right):
        metadata = lower_keys(load_json(meta)) # make all our keys lowercase since keys appear to change case (???)

        left_shape = get_image_shape(metadata, 'left')
        right_shape = get_image_shape(metadata, 'right')

        center_position = get_position(metadata) # (x, y, z) in meters
        fov = get_fov(metadata, center_position[2], left_shape) # (fov_x, fov_y) in meters; need to pass in the camera height to get correct fov

        left_position = [center_position[0]+STEREO_OFFSET, center_position[1], center_position[2]]
        right_position = [center_position[0]-STEREO_OFFSET, center_position[1], center_position[2]]

        left_gps_bounds = get_bounding_box_with_formula(left_position, fov) # (lat_max, lat_min, lng_max, lng_min) in decimal degrees
        right_gps_bounds = get_bounding_box_with_formula(right_position, fov)

        # check if this file is in the GPS bounds of interest
        #if left_gps_bounds[1] > bounds[0] and left_gps_bounds[0] < bounds[2] and left_gps_bounds[3] > bounds[1] and left_gps_bounds[2] < bounds[3]:
        left_baseName = os.path.basename(im_left)
        left_out = join(out_dir, left_baseName[:-3]+'jpg')
        left_image = process_image(left_shape, im_left, left_out)
        right_baseName = os.path.basename(im_right)
        right_out = join(out_dir, right_baseName[:-3]+'jpg')
        right_image = process_image(right_shape, im_right, right_out)

        left_tiff_out = join(out_dir,left_baseName[:-3]+'tif')
        create_geotiff('left', left_image, left_gps_bounds, left_tiff_out)
        right_tiff_out = join(out_dir,right_baseName[:-3]+'tif')
        create_geotiff('right', right_image, right_gps_bounds, right_tiff_out)
        # once we've saved the image, make sure to append this path to our list of TIFs
        with open(tif_list_file,'a+') as f:
            f.write(left_tiff_out + '\n')

def lower_keys(in_dict):
    if type(in_dict) is dict:
        out_dict = {}
        for key, item in in_dict.items():
            out_dict[key.lower()] = lower_keys(item)
        return out_dict
    elif type(in_dict) is list:
        return [lower_keys(obj) for obj in in_dict]
    else:
        return in_dict

def find_input_files(in_dir):
    json_suffix = os.path.join(in_dir, '*_metadata.json')
    jsons = glob(json_suffix)
    if len(jsons) == 0:
        fail('Could not find .json file')
        
        
    left_suffix = os.path.join(in_dir, '*_left.bin')
    lefts = glob(left_suffix)
    if len(lefts) == 0:
        fail('Could not find left.bin file')
    
    right_suffix = os.path.join(in_dir, '*_right.bin')
    rights = glob(right_suffix)
    if len(rights) == 0:
        fail('Could not find right.bin file')
    
    
    return jsons, lefts, rights

def load_json(meta_path):
    try:
        with open(meta_path, 'r') as fin:
            return json.load(fin)
    except Exception as ex:
        fail('Corrupt metadata file, ' + str(ex))

def get_image_shape(metadata, which):
    try:
        im_meta = metadata['sensor_variable_metadata']
        fmt = im_meta['image_format'][which]
        if fmt != 'BayerGR8':
            fail('Unknown image format: ' + fmt)
        width = im_meta['width_image_pixels'][which]
        height = im_meta['height_image_pixels'][which]
    except KeyError as err:
        fail('Metadata file missing key: ' + err.args[0])

    try:
        width = int(width)
        height = int(height)
    except ValueError as err:
        fail('Corrupt image dimension, ' + err.args[0])
    return (width, height)

def get_position(metadata):
    try:
        gantry_meta = metadata['gantry_variable_metadata']
        gantry_x = gantry_meta["position_m"]["x"]
        gantry_y = gantry_meta["position_m"]["y"]
        gantry_z = gantry_meta["position_m"]["z"]

        cam_meta = metadata['sensor_fixed_metadata']
        cam_x = cam_meta["location_in_camera_box_m"]["x"]
        cam_y = cam_meta["location_in_camera_box_m"]["y"]
        cam_z = cam_meta["location_in_camera_box_m"]["z"]
    except KeyError as err:
        fail('Metadata file missing key: ' + err.args[0])

    try:
        x = float(gantry_x) + float(cam_x)
        y = float(gantry_y) + float(cam_y)
        z = float(gantry_z) + float(cam_z)# + HEIGHT_MAGIC_NUMBER # gantry rails are at 2m
    except ValueError as err:
        fail('Corrupt positions, ' + err.args[0])
    return (x, y, z)

def get_fov(metadata, camHeight, shape):
    try:
        cam_meta = metadata['sensor_fixed_metadata']
        fov_x = cam_meta["field_of_view_at_2m_m"]["x"]
        fov_y = cam_meta["field_of_view_at_2m_m"]["y"]
    except KeyError as err:
        fail('Metadata file missing key: ' + err.args[0])

    try:
        #fov_list = fov.replace("[","").replace("]","").split()
        fov_x = 1.015 #float(fov_list[0])
        fov_y = 0.749 #float(fov_list[1])
        
        HEIGHT_MAGIC_NUMBER = 1.64
        PREDICT_MAGIC_SLOPE = 0.574
        predict_plant_height = PREDICT_MAGIC_SLOPE * camHeight
        camH_fix = camHeight + HEIGHT_MAGIC_NUMBER - predict_plant_height
        fix_fov_x = fov_x*(camH_fix/2)
        fix_fov_y = fov_y*(camH_fix/2)
        
        '''
        # test by Baker
        gantry_meta = metadata['lemnatec_measurement_metadata']['gantry_system_variable_metadata']
        gantry_z = gantry_meta["position z [m]"]
        fov_offset = (float(gantry_z) - 2) * FOV_MAGIC_NUMBER
        fov_y = fov_y*(FOV_IN_2_METER_PARAM + fov_offset)
        fov_x = (fov_y)/shape[1]*shape[0]
        

        # given fov is at 2m, so need to convert for actual height
        fov_x = (camHeight * (fov_x))/2
        fov_y = (camHeight * (fov_y))/2
        '''

    except ValueError as err:
        fail('Corrupt FOV inputs, ' + err.args[0])
    return (fix_fov_x, fix_fov_y)

def get_bounding_box(center_position, fov):
    # NOTE: ZERO_ZERO is the southeast corner of the field. Position values increase to the northwest (so +y-position = +latitude, or more north and +x-position = -longitude, or more west)
    # We are also simplifying the conversion of meters to decimal degrees since we're not close to the poles and working with small distances.

    # NOTE: x --> latitude; y --> longitude
    try:
        r = 6378137 # earth's radius

        x_min = center_position[1] - fov[1]/2
        x_max = center_position[1] + fov[1]/2
        y_min = center_position[0] - fov[0]/2
        y_max = center_position[0] + fov[0]/2

        lat_min_offset = y_min/r* 180/pi
        lat_max_offset = y_max/r * 180/pi
        lng_min_offset = x_min/(r * cos(pi * ZERO_ZERO[0]/180)) * 180/pi
        lng_max_offset = x_max/(r * cos(pi * ZERO_ZERO[0]/180)) * 180/pi

        lat_min = ZERO_ZERO[0] + lat_min_offset
        lat_max = ZERO_ZERO[0] + lat_max_offset
        lng_min = ZERO_ZERO[1] - lng_min_offset
        lng_max = ZERO_ZERO[1] - lng_max_offset
    except Exception as ex:
        fail('Failed to get GPS bounds from center + FOV: ' + str(ex))
    return (lat_min, lat_max, lng_max, lng_min)

def get_bounding_box_with_formula(center_position, fov):
    
    y_w = center_position[1] + fov[1]/2
    y_e = center_position[1] - fov[1]/2
    x_n = center_position[0] + fov[0]/2
    x_s = center_position[0] - fov[0]/2
    
    Mx_nw = ax + bx * x_n + cx * y_w
    My_nw = ay + by * x_n + cy * y_w
    
    Mx_se = ax + bx * x_s + cx * y_e
    My_se = ay + by * x_s + cy * y_e
    
    fov_nw_latlon = utm.to_latlon(Mx_nw, My_nw, SE_utm[2],SE_utm[3])
    fov_se_latlon = utm.to_latlon(Mx_se, My_se, SE_utm[2],SE_utm[3])
    
    return (fov_se_latlon[0] - lat_shift, fov_nw_latlon[0] - lat_shift, fov_nw_latlon[1] + lon_shift, fov_se_latlon[1] + lon_shift)

def process_image(shape, in_file, out_file=None):
    try:
        im = np.fromfile(in_file, dtype='uint8').reshape(shape[::-1])
        im_color = demosaic(im)
        im_color = (np.rot90(im_color))
        if out_file:
            Image.fromarray(im_color).save(out_file)
        return im_color
    except Exception as ex:
        fail('Error processing image "%s": %s' % (in_file, str(ex)))

def demosaic(im):
    # Assuming GBRG ordering.
    B = np.zeros_like(im)
    R = np.zeros_like(im)
    G = np.zeros_like(im)
    R[0::2, 1::2] = im[0::2, 1::2]
    B[1::2, 0::2] = im[1::2, 0::2]
    G[0::2, 0::2] = im[0::2, 0::2]
    G[1::2, 1::2] = im[1::2, 1::2]

    fG = np.asarray(
            [[0, 1, 0],
             [1, 4, 1],
             [0, 1, 0]]) / 4.0
    fRB = np.asarray(
            [[1, 2, 1],
             [2, 4, 2],
             [1, 2, 1]]) / 4.0

    im_color = np.zeros(im.shape+(3,), dtype='uint8') #RGB
    im_color[:, :, 0] = convolve(R, fRB)
    im_color[:, :, 1] = convolve(G, fG)
    im_color[:, :, 2] = convolve(B, fRB)
    return im_color

def create_geotiff(which_im, np_arr, gps_bounds, out_file_path):
    try:
        nrows,ncols,nz = np.shape(np_arr)
        # gps_bounds: (lat_min, lat_max, lng_min, lng_max)
        xres = (gps_bounds[3] - gps_bounds[2])/float(ncols)
        yres = (gps_bounds[1] - gps_bounds[0])/float(nrows)
        geotransform = (gps_bounds[2],xres,0,gps_bounds[1],0,-yres) #(top left x, w-e pixel resolution, rotation (0 if North is up), top left y, rotation (0 if North is up), n-s pixel resolution)

        output_raster = gdal.GetDriverByName('GTiff').Create(out_file_path, ncols, nrows, nz, gdal.GDT_Byte)

        output_raster.SetGeoTransform(geotransform) # specify coordinates
        srs = osr.SpatialReference() # establish coordinate encoding
        srs.ImportFromEPSG(4326) # specifically, google mercator
        output_raster.SetProjection( srs.ExportToWkt() ) # export coordinate system to file

        # TODO: Something wonky w/ uint8s --> ending up w/ lots of gaps in data (white pixels)
        output_raster.GetRasterBand(1).WriteArray(np_arr[:,:,0].astype('uint8')) # write red channel to raster file
        output_raster.GetRasterBand(1).FlushCache()
        output_raster.GetRasterBand(1).SetNoDataValue(-99)

        output_raster.GetRasterBand(2).WriteArray(np_arr[:,:,1].astype('uint8')) # write green channel to raster file
        output_raster.GetRasterBand(2).FlushCache()
        output_raster.GetRasterBand(2).SetNoDataValue(-99)

        output_raster.GetRasterBand(3).WriteArray(np_arr[:,:,2].astype('uint8')) # write blue channel to raster file
        output_raster.GetRasterBand(3).FlushCache()
        output_raster.GetRasterBand(3).SetNoDataValue(-99)

        output_raster = None
    except Exception as ex:
        fail('Error creating GeoTIFF: ' + str(ex))

def fail(reason):
    print >> sys.stderr, reason


if __name__ == '__main__':
    if len(sys.argv) != 4:
        fail('Usage: python %s <input_folder> <output_folder> <tif_list_file> <gps_bounds>' % sys.argv[0])
    retcode = main(*sys.argv[1:4])
