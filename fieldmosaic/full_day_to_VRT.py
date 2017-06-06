#!/usr/bin/env python

import os, sys, argparse
from glob import glob

# Example usage:
#   python full_day_to_VRT.py -d "2017-04-27"
#   python full_day_to_VRT.py -d "2017-04-15" -s "hyperspectral" -p "*.nc"
#   python full_day_to_VRT.py -d "2017-05-20" -s "flir2tif" -o "flirIrCamera"



def options():
    
    parser = argparse.ArgumentParser(description='Full Field Stitching Extractor in Roger',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument("-i", "--in_root", help="input, stereo top bin files parent directory",
                        default="/home/extractor/sites/ua-mac/Level_1/")
    parser.add_argument("-d", "--date", help="scan date")
    parser.add_argument("-s", "--source", help="name of input geotiff directory", default="stereoTop_geotiff")
    parser.add_argument("-o", "--out", help="name of output prefix (fullfield/date/prefix_fullfield)", default="stereoTop")
    parser.add_argument("-p", "--pattern", help="file pattern to match",
                        default='*(Left).tif')
    parser.add_argument("--relative", help="store relative path names in VRT",
                        default=True)

    args = parser.parse_args()

    return args

def main():
    args = options()
    if os.path.exists(os.path.join(args.in_root, args.source)):
        in_dir = os.path.join(args.in_root, args.source, args.date)
    else:
        in_dir = os.path.join(args.in_root, args.source, args.date)
    out_dir = os.path.join(args.in_root, "fullfield", args.date)

    if not os.path.isdir(in_dir):
        return
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    # Create a file to write the paths for all of the TIFFs. This will be used create the VRT.
    file_list = os.path.join(out_dir, args.out+'_fileList.txt')
    if os.path.exists(file_list):
        try:
            os.remove(file_list) # start from a fresh list of TIFFs for the day
        except OSError:
            pass

    print "Fetching list of GeoTIFFs..."
    subdirs = os.listdir(in_dir)
    f = open(file_list,'w')
    for subdir in subdirs:
        buildFileList(os.path.join(in_dir,subdir), out_dir, f, args.pattern, args.relative, args.source, args.date)
    f.close()
    
    # Create VRT from every GeoTIFF
    print "Starting VRT creation..."
    createVrtPermanent(out_dir,file_list, args.out+"_fullfield.VRT", args.relative)
    print "Completed VRT creation..."

def find_input_files(in_dir, pattern):
    left_suffix = os.path.join(in_dir, pattern)
    files = glob(left_suffix)
    if len(files) == 0:
        fail('Could not find input files')

    return files

def buildFileList(in_dir, out_dir, list_obj, pattern, relative, sensor, date):
    if not os.path.isdir(in_dir):
        fail('Could not find input directory: ' + in_dir)
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    files = find_input_files(in_dir, pattern)

    for fname in files:
        if relative:
            # <up from date>/<up from fullfield>/
            fname = "../../"+sensor+"/"+date+"/"+os.path.basename(fname)
        list_obj.write(fname + '\n')

def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i+1

def createVrtPermanent(base_dir, file_list, out_vrt, relative):
    # Create virtual tif for the files in this folder
    # Build a virtual TIF that combines all of the tifs that we just created
    print "\tCreating virtual TIF..."
    try:
        if relative:
            os.chdir(base_dir)
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
