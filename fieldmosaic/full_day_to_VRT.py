#!/usr/bin/env python

import os, sys, argparse
from glob import glob

# Example usage:
#   python full_day_to_VRT.py -d "2017-04-27"
#   python full_day_to_VRT.py -d "2017-04-15" -s "hyperspectral" -p "*.nc"



def options():
    
    parser = argparse.ArgumentParser(description='Full Field Stitching Extractor in Roger',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument("-i", "--in_root", help="input, stereo top bin files parent directory",
                        default="/home/extractor/sites/ua-mac/Level_1/")
    parser.add_argument("-d", "--date", help="scan date")
    parser.add_argument("-s", "--sensor", help="sensor name", default="stereoTop")
    parser.add_argument("-p", "--pattern", help="file pattern to match",
                        default='*(Left).tif')

    args = parser.parse_args()

    return args

def main():
    args = options()
    if os.path.exists(os.path.join(args.in_root, args.sensor+"_geotiff")):
        in_dir = os.path.join(args.in_root, args.sensor+"_geotiff", args.date)
    else:
        in_dir = os.path.join(args.in_root, args.sensor, args.date)
    out_dir = os.path.join(args.in_root, "fullfield", args.date)

    if not os.path.isdir(in_dir):
        return
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    # Create a file to write the paths for all of the TIFFs. This will be used create the VRT.
    file_list = os.path.join(out_dir, args.sensor+'_fileList.txt')
    if os.path.exists(file_list):
        try:
            os.remove(file_list) # start from a fresh list of TIFFs for the day
        except OSError:
            pass

    print "Fetching list of GeoTIFFs..."
    subdirs = os.listdir(in_dir)
    f = open(file_list,'w')
    for subdir in subdirs:
        buildFileList(os.path.join(in_dir,subdir), out_dir, f, args.pattern)
    f.close()
    
    # Create VRT from every GeoTIFF
    print "Starting VRT creation..."
    createVrtPermanent(out_dir,file_list, args.sensor+"_fullfield.VRT")
    print "Completed VRT creation..."

def find_input_files(in_dir, pattern):
    left_suffix = os.path.join(in_dir, pattern)
    files = glob(left_suffix)
    if len(files) == 0:
        fail('Could not find input files')

    return files

def buildFileList(in_dir, out_dir, list_obj, pattern):
    if not os.path.isdir(in_dir):
        fail('Could not find input directory: ' + in_dir)
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    files = find_input_files(in_dir, pattern)

    for fname in files:
        list_obj.write(fname + '\n')

def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i+1

def createVrtPermanent(base_dir, file_list, out_vrt):
    # Create virtual tif for the files in this folder
    # Build a virtual TIF that combines all of the tifs that we just created
    print "\tCreating virtual TIF..."
    try:
        vrtPath = os.path.join(base_dir, out_vrt)
        cmd = 'gdalbuildvrt -srcnodata "-99 -99 -99" -overwrite -input_file_list ' + file_list +' ' + vrtPath
        print(cmd)
        os.system(cmd)
    except Exception as ex:
        fail("\tFailed to create virtual tif: " + str(ex))

def fail(reason):
    print >> sys.stderr, reason

if __name__ == '__main__':
    
    main()
