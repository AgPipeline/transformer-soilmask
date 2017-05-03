#!/usr/bin/env python

import os, sys, argparse
from glob import glob

# Example usage: python full_day_to_VRT.py -d "2017-04-27"


def options():
    
    parser = argparse.ArgumentParser(description='Full Field Stitching Extractor in Roger',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument("-i", "--in_dir", help="input, stereo top bin files parent directory",
                        default="/home/extractor/sites/ua-mac/Level_1/stereoTop_geotiff/")
    parser.add_argument("-o", "--out_dir", help="output parent directory",
                        default="/home/extractor/sites/ua-mac/Level_1/fullfield/")
    parser.add_argument("-d", "--date", help="scan date")

    args = parser.parse_args()

    return args

def main():
    args = options()
    in_dir = os.path.join(args.in_dir, args.date)
    out_dir = os.path.join(args.out_dir, args.date)

    if not os.path.isdir(in_dir) or not os.path.isdir(args.out_dir):
        return
    os.makedirs(out_dir)

    # Create a file to write the paths for all of the TIFFs. This will be used create the VRT.
    tif_file_list = os.path.join(out_dir, args.date, 'stereoTop_tifList.txt')
    if os.path.exists(tif_file_list):
        try:
            os.remove(tif_file_list) # start from a fresh list of TIFFs for the day
        except OSError:
            pass

    print "Fetching list of GeoTIFFs..."
    subdirs = os.listdir(in_dir)
    for subdir in subdirs:
        buildTifList(subdir, out_dir, tif_file_list)
    
    # Create VRT from every GeoTIFF
    print "Starting VRT creation..."
    createVrtPermanent(out_dir,tif_file_list)
    print "Completed VRT creation..."

def find_input_files(in_dir):
    left_suffix = os.path.join(in_dir, '*(Left).tif')
    lefts = glob(left_suffix)
    if len(lefts) == 0:
        fail('Could not find left.tif files')

    return lefts

def buildTifList(in_dir, out_dir, tif_list_file):
    if not os.path.isdir(in_dir):
        fail('Could not find input directory: ' + in_dir)
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    ims_left = find_input_files(in_dir)

    f = open(tif_list_file,'a+')
    for im_left in ims_left:
        f.write(im_left + '\n')
    f.close()

def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i+1

def createVrtPermanent(base_dir, tif_file_list, out_vrt="stereoTop_fullfield.VRT"):
    # Create virtual tif for the files in this folder
    # Build a virtual TIF that combines all of the tifs that we just created
    print "\tCreating virtual TIF..."
    try:
        vrtPath = os.path.join(base_dir, out_vrt)
        cmd = 'gdalbuildvrt -srcnodata "-99 -99 -99" -overwrite -input_file_list ' + tif_file_list +' ' + vrtPath
        print(cmd)
        os.system(cmd)
    except Exception as ex:
        fail("\tFailed to create virtual tif: " + str(ex))

def fail(reason):
    print >> sys.stderr, reason

if __name__ == '__main__':
    
    main()
