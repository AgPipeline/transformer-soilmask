'''
Created on Oct 31, 2016

@author: Zongyang
'''
import os, sys, json
from glob import glob
from PIL import Image, ImageFilter
from scipy.ndimage.filters import convolve
import numpy as np
import terra_common
import matplotlib.pyplot as plt
from datetime import date


def main():
    
    return

# Utility functions for modularity between command line and extractors
###########################################
def get_traits_table():
    # Compiled traits table
    fields = ('local_datetime', 'canopy_cover', 'access_level', 'species', 'site',
              'citation_author', 'citation_year', 'citation_title', 'method')
    traits = {'local_datetime' : '',
              'canopy_cover' : [],
              'access_level': '2',
              'species': 'Sorghum bicolor',
              'site': [],
              'citation_author': '"Zongyang, Li"',
              'citation_year': '2016',
              'citation_title': 'Maricopa Field Station Data and Metadata',
              'method': 'Canopy Cover Estimation from RGB images'}

    return (fields, traits)

def generate_traits_list(traits):
    # compose the summary traits
    trait_list = [  traits['local_datetime'],
                    traits['canopy_cover'],
                    traits['access_level'],
                    traits['species'],
                    traits['site'],
                    traits['citation_author'],
                    traits['citation_year'],
                    traits['citation_title'],
                    traits['method']
                ]

    return trait_list

def generate_cc_csv(fname, fields, trait_list):
    """ Generate CSV called fname with fields and trait_list """
    csv = open(fname, 'w')
    csv.write(','.join(map(str, fields)) + '\n')
    csv.write(','.join(map(str, trait_list)) + '\n')
    csv.close()

    return fname

def find_input_files(in_dir):
    
    json_suffix = os.path.join(in_dir, '*_metadata.json')
    jsons = glob(json_suffix)
    if len(jsons) == 0:
        terra_common.fail('Could not find .json file')
        return [], []
        
        
    bin_suffix = os.path.join(in_dir, '*left.bin')
    bins = glob(bin_suffix)
    if len(bins) == 0:
        terra_common.fail('Could not find .bin file')
        return [], []
    
    return jsons[0], bins[0]

def get_plot_num(meta):
    
    center_position = parse_metadata(meta)
    
    convt = terra_common.CoordinateConverter()
    
    plot_row, plot_col = convt.fieldPosition_to_fieldPartition(center_position[0], center_position[1])
    
    plotNum = convt.fieldPartition_to_plotNum(plot_row, plot_col)
    
    return plotNum

def parse_metadata(metadata):
    
    try:
        gantry_meta = metadata['lemnatec_measurement_metadata']['gantry_system_variable_metadata']
        gantry_x = gantry_meta["position x [m]"]
        gantry_y = gantry_meta["position y [m]"]
        gantry_z = gantry_meta["position z [m]"]
        
        
        cam_meta = metadata['lemnatec_measurement_metadata']['sensor_fixed_metadata']
        cam_x = cam_meta["location in camera box x [m]"]
        cam_y = cam_meta["location in camera box y [m]"]
        
        
        if "location in camera box z [m]" in cam_meta: # this may not be in older data
            cam_z = cam_meta["location in camera box z [m]"]
        else:
            cam_z = 0

    except KeyError as err:
        terra_common.fail('Metadata file missing key: ' + err.args[0])
        
    position = [float(gantry_x), float(gantry_y), float(gantry_z)]
    center_position = [position[0]+float(cam_x), position[1]+float(cam_y), position[2]+float(cam_z)]
    
    return center_position

def get_localdatetime(metadata):
    try:
        gantry_meta = metadata['lemnatec_measurement_metadata']['gantry_system_variable_metadata']
        localTime = gantry_meta["time"]
    except KeyError as err:
        terra_common.fail('Metadata file missing key: ' + err.args[0])
        
    return localTime


def get_CC_from_bin(file_path):
    
    image = process_image(file_path, [3296, 2472])
    
    lei = gen_cc_for_img(image, 5)
    
    return lei

def gen_cc_for_img(img, kernelSize):
    
    #im = Image.fromarray(img)
    
    #r, g, b = im.split()
    
    r = img[:,:,0]
    g = img[:,:,1]
    b = img[:,:,2]
    
    sub_img = (g.astype('int') - r.astype('int') - 2) > 0
    
    mask = np.zeros_like(b)
    
    mask[sub_img] = 255
    
    im = Image.fromarray(mask)
    blur = im.filter(ImageFilter.BLUR)
    pix = np.array(blur)
    #blur = cv2.blur(mask,(kernelSize,kernelSize))
    sub_mask = pix > 128
    
    c = np.count_nonzero(sub_mask)
    ratio = c/float(b.size)
    
    return ratio

def process_image(im_path, shape):
    im = np.fromfile(im_path, dtype='uint8').reshape(shape[::-1])
    im_color = demosaic(im)
    im_color = np.rot90(im_color)
    #out_path = im_path[:-4] + '.jpg'
    #Image.fromarray(im_color).save(out_path)
    return im_color

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

def load_json(meta_path):
    try:
        with open(meta_path, 'r') as fin:
            return json.load(fin)
    except Exception as ex:
        fail('Corrupt metadata file, ' + str(ex))
    
    
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

def fail(reason):
    print >> sys.stderr, reason

if __name__ == "__main__":

    main()