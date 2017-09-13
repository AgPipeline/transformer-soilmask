'''
Created on May 24, 2017

@author: Zongyang
'''
import os, multiprocessing,sys
import gdal2tiles_parallel
import bin_to_geotiff
import geotiff_to_tiles
import numpy as np
import cv2
import shutil
try:
    from osgeo import gdal
    from osgeo import osr
except:
    import gdal
    print('You are using "old gen" bindings. gdal2tiles needs "new gen" bindings.')
    sys.exit(1)
    

# Define that GPS bounds of interest -- we'll ignore any data that are outside of these bounds
# Order is: (SW_lat,SW_lng,NE_lat,NE_lng)
# full field
GPS_BOUNDS = (33.072616729424254, -111.97499111294746, 33.07404171941707, -111.9747644662857)
baseTileLevel = 28 # base tile level should be constant for all the process
TILE_FOLDER_NAME = 'tiles_left'

# split tif_list file into 'split_num' different files
def split_tif_list(tif_list, out_dir, split_num):
    
    if not os.path.exists(tif_list):
        return
    
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)
    
    out_txt_vec = []
    for i in range(0, split_num):
        if not os.path.isdir(os.path.join(out_dir, str(i))):
            os.mkdir(os.path.join(out_dir, str(i)))
        out_file_path = os.path.join(out_dir, str(i), 'tif_list.txt')
        out_file_handle = open(out_file_path, 'w')
        out_txt_vec.append(out_file_handle)
    
    file_handle = open(tif_list, 'r')
    
    lines = file_handle.readlines()
    
    for i in range(0,len(lines)):
        file_index = i % split_num
        out_txt_vec[file_index].write(lines[i])
            
    for i in range(0, split_num):
        out_txt_vec[i].close()
    
    return

# use gdal2tiles_parallel to create different tiles set
def create_diff_tiles_set(out_dir, split_num):
    
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)
    
    for i in range(split_num):
        tif_list = os.path.join(out_dir, str(i), 'tif_list.txt')
        if not os.path.exists(tif_list):
            continue
        
        child_out_dir = os.path.join(out_dir, str(i))
        if not os.path.isdir(child_out_dir):
            os.mkdir(child_out_dir)
            
        # Create VRT from every GeoTIFF
        geotiff_to_tiles.createVrt(child_out_dir,tif_list)
    
        # Generate tiles from VRT
        geotiff_to_tiles.createMapTiles(child_out_dir,multiprocessing.cpu_count())
    
        # Generate google map html template
        # geotiff_to_tiles.generate_googlemaps(child_out_dir, 'tiles_left')
    
    return

# using base tiles to create overview tiles
def create_unite_tiles(out_dir, vrtPath):
    
    NUM_THREADS = multiprocessing.cpu_count()
    
    cmd = 'gdal2tiles_parallel.py --processes=' + str(NUM_THREADS) + ' -n -e -p geodetic -f JPEG -z 18-28 -s EPSG:4326 ' + vrtPath + ' ' + os.path.join(out_dir,'tiles_left')
    argv = cmd.split()
    
    gdal2tiles = gdal2tiles_parallel.GDAL2Tiles(argv[1:])
    
    tminz ,tmaxz = gdal2tiles_parallel.getZooms(gdal2tiles)
    
    print("Generating Overview Tiles:")
    for tz in range(tmaxz-1, tminz-1, -1):
        #print("\tGenerating for zoom level: " + str(tz))
        gdal2tiles_parallel.worker_overview_tiles(argv[1:], 0, tz)
        '''
        pool = multiprocessing.Pool()
        for cpu in range(gdal2tiles.options.processes):
            pool.apply_async(gdal2tiles_parallel.worker_overview_tiles, [argv, cpu, tz])
        pool.close()
        pool.join()
        '''
        #print("\tZoom level " + str(tz) + " complete.")
        
    # Generate google map html template
    #geotiff_to_tiles.generate_googlemaps(out_dir, 'tiles_left')
    
    return

# choose a darker pixel from several base tiles data set, to create a new united base tile, ignore black area 
def integrate_tiles(in_dir, out_dir, split_num, tiles_folder_name='tiles_left'):
    
    # get source images
    baseSrcDir = os.path.join(in_dir, '0', tiles_folder_name, str(baseTileLevel))
    list_dirs = os.walk(baseSrcDir)
    for root, dirs, files in list_dirs:
        for d in dirs:
            #print("Start processing "+ d)
            i_path = os.path.join(baseSrcDir, d)
            if not os.path.isdir(i_path):
                continue
            
            list_files = os.walk(i_path)
            for sRoot, sDirs, sFiles in list_files:
                for f in sFiles:
                    tile_path_list = []
                    # fill tile path into a list
                    for i in range(split_num):
                        tile_path = os.path.join(in_dir, str(i), tiles_folder_name, str(baseTileLevel), d, f)
                        if not os.path.exists(tile_path):
                            break
                        tile_path_list.append(tile_path)
                    
                    # for not paired tiles, just copy files
                    if len(tile_path_list) < split_num:
                        dst_dir = os.path.join(out_dir, tiles_folder_name, str(baseTileLevel), d)
                        if not os.path.isdir(dst_dir):
                            os.makedirs(dst_dir)
                        
                        dst_path = os.path.join(dst_dir, f)
                        src_path = tile_path_list[0]
                        shutil.copyfile(src_path, dst_path)
                        continue
                    
                    # generate a target tile image
                    out_img = create_new_tiles_fast(tile_path_list)
    
                    # save output image
                    dst_dir = os.path.join(out_dir, tiles_folder_name, str(baseTileLevel), d)
                    if not os.path.isdir(dst_dir):
                        os.makedirs(dst_dir)
                        
                    dst_path = os.path.join(dst_dir, f)
                    cv2.imwrite(dst_path, out_img)
    
    return

def copy_missing_tiles(in_dir, out_dir, split_num, tiles_folder_name='tiles_left'):
    
    for i in range(split_num):
        src_dir = os.path.join(in_dir, str(i), tiles_folder_name, str(baseTileLevel))
        
        list_dirs = os.listdir(src_dir)
        for d in list_dirs:
            i_path = os.path.join(src_dir, d)
            list_files = os.walk(i_path)
            for sRoot, sDirs, sFiles in list_files:
                for f in sFiles:
                    dst_dir = os.path.join(out_dir, tiles_folder_name, str(baseTileLevel), d)
                    dst_file = os.path.join(out_dir, tiles_folder_name, str(baseTileLevel), d, f)
                    if not os.path.exists(dst_file):
                        if not os.path.isdir(dst_dir):
                            os.makedirs(dst_dir)
                        src_file = os.path.join(i_path, f)
                        shutil.copyfile(src_file, dst_file)
    
    return

# choose darkest pixel from tile list to create a new tile file
def create_new_tiles(tile_path_list):
    
    img_list = []
    hsv_list = []
    
    for file_path in tile_path_list:
        img = cv2.imread(file_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        v = hsv[:,:,2]
        img_list.append(img)
        hsv_list.append(v)
        
    height, width = img_list[0].shape[:2]
    ret_img = np.zeros_like(img_list[0])
    
    for i in range(height):
        for j in range(width):
            ind = 0
            val = 256
            for k in range(len(hsv_list)):
                if hsv_list[k][i,j] < val:
                    if hsv_list[k][i,j] < 2:
                        continue
                    val = hsv_list[k][i,j]
                    ind = k
            
            if ind in range(len(hsv_list)):
                ret_img[i,j, :] = img_list[ind][i,j,:]
    
    
    return ret_img

# a faster version
def create_new_tiles_fast(tile_path_list):
    
    img_list = []
    hsv_list = []
    
    for file_path in tile_path_list:
        img = cv2.imread(file_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        v = hsv[:,:,2]
        img_list.append(img)
        hsv_list.append(v)
        
    ret_img = np.zeros_like(img_list[0])
    
    if len(img_list) == 2:
        mask1 = hsv_list[0] < hsv_list[1]
        mask2 = hsv_list[0] > 1
        mask3 = hsv_list[1] < 2
        mask = mask1 & mask2
        mask = mask | mask3
        input_mask = np.zeros_like(hsv_list[0])
        input_mask_ = np.zeros_like(hsv_list[0])
        input_mask[mask] = 255
        
        mask_ = np.logical_not(mask)
        input_mask_[mask_] = 255
        img0 = cv2.bitwise_and(img_list[0],img_list[0],mask = input_mask)
        img1 = cv2.bitwise_and(img_list[1],img_list[1],mask = input_mask_)
        
        ret_img = cv2.add(img0, img1)
        
    return ret_img


def main():
    src_bin_dir = '/Users/Desktop/pythonTest/stitch_map/2017-05-27'
    in_dir = '/Users/Desktop/pythonTest/rogerFS/2017-05-27/'
    out_dir = '/Users/Desktop/pythonTest/shadeRemoval/2017-05-27'
    
    create_tif_list(src_bin_dir, in_dir)
    
    darker_tiles_generator(in_dir, out_dir)
    
    return

def create_tif_list(in_dir, out_dir):
    
    if not os.path.isdir(in_dir):
        return
    
    subdirs = os.listdir(in_dir)

    # Create a file to write the paths for all of the TIFFs. This will be used create the VRT.
    tif_file_list = os.path.join(out_dir,'tif_list.txt')
    
    
    # If there is a pre-existing tiles folder with this name, delete it (failing to do so can result in some weirdness when you load tiles later)
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    
    os.makedirs(out_dir)
    
    if os.path.exists(tif_file_list):
        try:
            os.remove(tif_file_list) # start from a fresh list of TIFFs for the day
        except OSError:
            pass

    # Convert binary files that are within GPS bounds to JPGs and GeoTIFFs
    print "Starting binary to image conversion..."
    for subdir in subdirs:
        in_path = os.path.join(in_dir, subdir)
        out_path = os.path.join(out_dir, subdir)
        try:
            bin_to_geotiff.main(in_path,out_path,tif_file_list, GPS_BOUNDS)
        except Exception as ex:
            fail("\tFailed to process folder %s: %s" % (in_path, str(ex)))
    print "Completed binary to image conversion..."
    print "Found " + str(file_len(tif_file_list)) + " folders within GPS bounds."
    
    
    # Create VRT from every GeoTIFF
    print "Starting VRT creation..."
    geotiff_to_tiles.createVrt(out_dir,tif_file_list)
    print "Completed VRT creation..."
    
    return

def darker_tiles_generator(in_dir, out_dir):
    
    split_num = 2
    
    tif_list = os.path.join(in_dir, 'tif_list.txt')
    if not os.path.exists(tif_list):
        return
    
    split_tif_list(tif_list, out_dir, split_num)
    
    create_diff_tiles_set(out_dir, split_num)
    
    unite_tiles_dir = os.path.join(out_dir, 'unite')
    integrate_tiles(out_dir, unite_tiles_dir, split_num)
    
    copy_missing_tiles(out_dir, unite_tiles_dir, split_num, tiles_folder_name='tiles_left')
    
    src_vrt_path = os.path.join(in_dir, 'virtualTif.vrt')
    create_unite_tiles(unite_tiles_dir, src_vrt_path)
    
    return

def fail(reason):
    print >> sys.stderr, reason
    
def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i+1

if __name__ == '__main__':
    
    main()

