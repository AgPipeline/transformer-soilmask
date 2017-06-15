'''
Created on Mar 21, 2017

@author: Zongyang
'''
import os, sys, calibration, json, argparse
import numpy as np
from PIL import Image, ImageFilter
import matplotlib.pyplot as plt
from glob import glob
import terra_common
from scipy.ndimage.filters import convolve
from scipy.stats.stats import pearsonr
import cv2
from datetime import date


def main():
    '''
    args = options()

    if args.mode == 'one':
        full_day_stereo_to_height(args.calib_dir, args.in_dir, args.out_dir)
            
        stereo_height_data_integrate_per_day(args.out_dir, args.out_dir)
        
    if args.mode == 'date':
        process_one_month_data(args.calib_dir, args.in_dir, args.out_dir)
    
    return
    '''
    '''
    boardSize = (7,7)
    squareSize = 5.6
    img_size = (3296, 2472)
    stereo_calibrate(in_dir, boardSize, squareSize, img_size, calib_dir)
    
    in_dir = '/Users/nijiang/Desktop/pythonTest/stereoTop/2016-10-16'
    out_dir = '/Users/nijiang/Desktop/pythonTest/stereoToHeight/2016-10-16-2'
    calib_dir = '/Users/nijiang/Desktop/pythonTest/stereoTop/calibResult'
    '''
    
    '''
    in_dir = '/projects/arpae/terraref/sites/ua-mac/raw_data/stereoTop/2016-10-16'
    out_dir = '/projects/arpae/terraref/users/zongyang/stereoToHeight/2016-10-16'
    calib_dir = '/home/zongyang/stereo_height/codes/calibResult'
    #stereo_image_to_disparity(calib_dir, in_dir, out_dir)
    full_day_stereo_to_height(calib_dir, in_dir, out_dir)
    stereo_height_data_integrate_per_day(out_dir, out_dir)
    '''
    #compare_hists('/Users/nijiang/Desktop/heightDistribution/origin_updated_height/10-16_3dTop_height.npy',
    compare_hists('/Users/nijiang/Desktop/heightDistribution/origin_updated_height/10-16_3dTop_height.npy','/Users/nijiang/Desktop/pythonTest/stereoToHeight/stereoResult/2016-10-16_stereoHeight.npy', '/Users/nijiang/Desktop/pythonTest/stereoToHeight/10-16-plots')
    
    return

def options():
    
    parser = argparse.ArgumentParser(description='Stereo image to height on Roger',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument("-m", "--mode", help="all day flag, date for special days' process, given parent directory as input, one for one day process")
    parser.add_argument("-i", "--in_dir", help="input directory")
    parser.add_argument("-o", "--out_dir", help="output directory")
    parser.add_argument("-c", "--calib_dir", help="calibration directory")

    args = parser.parse_args()

    return args

def process_one_month_data(calib_dir, in_dir, out_dir):
    
    for day in range(11, 21):
        target_date = date(2016, int(10), day)
        str_date = target_date.isoformat()
        print(str_date)
        in_path = os.path.join(in_dir, str_date)
        out_path = os.path.join(out_dir, str_date)
        if not os.path.isdir(in_path):
            continue
        try:
            full_day_stereo_to_height(calib_dir, in_path, out_path)
    
            stereo_height_data_integrate_per_day(out_path, out_path)
        except Exception as ex:
            fail(str_date + str(ex))
    
    return

def compare_hists(histfile1, histfile2, out_dir):
    
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    
    hist1 = np.load(histfile1)
    hist2 = np.load(histfile2)
    
    z_shift = 0
    hist2_new = np.concatenate((hist2[:,z_shift:], hist2[:,:z_shift]), axis=1)
    
    for j in range(89, 90):
        plot_quantiles_level(hist1, hist2_new, j/100.0, out_dir)
    
    for i in range(50, 250):
        draw_height_plot(i, hist1, hist2_new, out_dir)
    
    return

def plot_quantiles_level(hist1, hist2, quantile, out_dir):
    
    fig, ax = plt.subplots()
    a = []
    b = []
    
    for i in range(1, 1650):
        #if not remove_left_bound_data(i):
        #    continue
        
        y1 = get_quantile(hist1[i], quantile)
        y2 = get_quantile(hist2[i], quantile)
        
        if y1 == 0 or y2 == 0:
            continue
        
        a.append(y1)
        b.append(y2)
        
        #print np.corrcoef(hist1[i], hist2[i])
        
        #plt.bar(i, y1, width=0.6, color='blue')
        #plt.bar(i+0.4, y2, width=0.6, color='red')
        ax.scatter(y1, y2, c='blue',alpha=0.5, edgecolors='none')
        
    c = pearsonr(a, b)
    print quantile
    print c
    
    plt_title = 'With Soil Remove'
    plt.xlabel('Scanner 3d height')
    plt.ylabel('Stereo height')
    plt.title(plt_title)
    
    out_file = os.path.join(out_dir, str(quantile)+'.png')
    plt.savefig(out_file)
    plt.close()
    
    return

def remove_left_bound_data(plotNum):
    
    div_num = (plotNum + 1) % 64
    if div_num < 4:
        return False
    else:
        return True
    
    

def get_quantile(hist, level):
    
    targetHist = hist
    targetHist = targetHist/np.sum(targetHist)
    quantiles = np.cumsum(targetHist)
    b=np.arange(len(quantiles))
    c=b[quantiles>level]
    if len(c) == 0:
        return 0
    quantile = min(c)
    '''
    d=b[quantiles<=0.0001]
    if len(d) == 0:
        return 0
    '''
    quantile_0 = 0#max(d)
    estHeight = quantile - quantile_0
    
    return estHeight

def full_day_stereo_to_height(calib_dir, in_dir, out_dir):
    
    # load camera intrinsic parameters
    calib = calibration.StereoCalibration()
    calib.load(calib_dir)
    
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    
    list_dirs = os.walk(in_dir)
    for root, dirs, files in list_dirs:
        for d in dirs:
            i_path = os.path.join(in_dir, d)
            o_path = os.path.join(out_dir, d)
            if not os.path.isdir(i_path):
                continue
            
            if not os.path.isdir(o_path):
                os.mkdir(o_path)
            else:
                continue
            
            try:
                generate_meta_height_hist(i_path, o_path, calib)
            except Exception as ex:
                fail(i_path + str(ex))

    return

def stereo_height_data_integrate_per_day(in_dir, out_dir):
    
    list_dirs = os.walk(in_dir)
    heightHist = np.zeros((1728, 400))
    
    for root, dirs, files in list_dirs:
        for d in dirs:
            i_path = os.path.join(in_dir, d)
            if not os.path.isdir(i_path):
                continue
            
            plotNum, hist = draw_meta_hist_data(i_path)
            
            for j in range(0,len(plotNum)):
                heightHist[plotNum[j]-1] = heightHist[plotNum[j]-1]+hist[j]
    
    histfile = os.path.join(out_dir, 'heightHist.npy')
    np.save(histfile, heightHist)
    
    hist_out_file = os.path.join(out_dir, 'hist.txt')
    np.savetxt(hist_out_file, np.array(heightHist), delimiter="\t")
    
    return

def draw_height_plot(plotNum, hist1, hist2, out_dir):
    
    fig, ax = plt.subplots()
    sum_num = 5
    plotHist1 = hist1[plotNum]
    histSum1 = 0
    y = np.arange(plotHist1.size/sum_num)
    for i in range(plotHist1.size/sum_num):
        metaSum = np.sum(plotHist1[i*sum_num:(i+1)*sum_num])
        if metaSum > histSum1:
            histSum1 = metaSum
            
    for i in range(plotHist1.size/sum_num):
        plotData = np.sum(plotHist1[i*sum_num:(i+1)*sum_num])/histSum1
        plt.bar(y[i]+0.4, plotData, width=0.6, bottom=None, hold=None, data=None, color='blue')
    
    plotHist2 = hist2[plotNum]
    histSum2 = 0
    y = np.arange(plotHist2.size/sum_num)
    for i in range(plotHist2.size/sum_num):
        metaSum = np.sum(plotHist2[i*sum_num:(i+1)*sum_num])
        if metaSum > histSum2:
            histSum2 = metaSum
    
    for i in range(plotHist2.size/sum_num):
        plotData = np.sum(plotHist2[i*sum_num:(i+1)*sum_num])/histSum2
        plt.bar(y[i], plotData, width=0.6, bottom=None, hold=None, data=None, color='red')
    
    plt_title = 'Plot Number:%d' % plotNum
    plt.xlabel('height level')
    plt.ylabel('Point sum')
    plt.title(plt_title)
    
    out_file = '%d_plot.png' % plotNum
    out_file = os.path.join(out_dir, out_file)
    plt.savefig(out_file)
    plt.close()
    
    return

def draw_meta_hist_data(in_dir):
    
    npy_suffix = os.path.join(in_dir, '*.npy')
    npys = glob(npy_suffix)
    if len(npys) == 0:
        fail('No numpy file found in input directory.')
        return [], []
    
    hist_data = []
    plots = []
    for hist_file in npys:
        file_name = os.path.basename(hist_file)
        if not os.path.exists(hist_file):
            continue
        
        plotNum = (file_name[:-4])
        hist = np.load(hist_file, 'r')
        plots.append(int(plotNum))
        hist_data.append(hist)
    
    return plots, hist_data

def stereo_image_to_disparity(calib_dir, image_dir, out_dir):
    
    # load camera intrinsic parameters
    calib = calibration.StereoCalibration()
    calib.load(calib_dir)
    
    # compute and display rectification
    list_dirs = os.walk(image_dir)
    for root, dirs, files in list_dirs:
        for d in dirs:
            i_path = os.path.join(image_dir, d)
            if not os.path.isdir(i_path):
                continue
            
            left_file = os.path.join(i_path, 'left.jpg')
            right_file = os.path.join(i_path, 'right.jpg')
            
            left_img = cv2.imread(left_file) #cv2.cvtColor(cv2.imread(left_file), cv2.COLOR_BGR2GRAY)
            right_img = cv2.imread(right_file) #cv2.cvtColor(cv2.imread(right_file), cv2.COLOR_BGR2GRAY)
            
            
            
            frames = []
            frames.append(left_img)
            frames.append(right_img)
            
            newFrame = calib.rectify(frames)
            
            imgL = cv2.pyrDown(cv2.pyrDown( newFrame[0] ))
            imgR = cv2.pyrDown(cv2.pyrDown( newFrame[1] ))
            
            cv2.imwrite(os.path.join(i_path, 'rectify0.png'), newFrame[0])
            cv2.imwrite(os.path.join(i_path, 'rectify1.png'), newFrame[1])
    
            # disparity range is tuned for 'aloe' image pair
            window_size = 9
            min_disp = 1
            num_disp = 321-min_disp
            stereo = cv2.StereoSGBM(minDisparity = min_disp,
                numDisparities = num_disp,
                SADWindowSize = window_size,
                uniquenessRatio = 2,
                speckleWindowSize = 50,
                speckleRange = 3,
                disp12MaxDiff = 3,
                P1 = 8*window_size*window_size,
                P2 = 32*window_size*window_size,
                fullDP = False
            )
        
            print 'computing disparity...'
            disp1 = stereo.compute(imgL, imgR).astype(np.float32) / 16.0
            #disp = cv2.pyrUp(cv2.pyrUp(disp1))
            disp = disp1#cv2.resize(disp1, (3296, 2472),0, 0, cv2.INTER_AREA)
            cv2.imwrite(os.path.join(i_path, 'disp.png'), disp)
            
            Q = calib.disp_to_depth_mat
            Q[2][3] = Q[2][3] / 4.0 # it was 6700 by calibration
            #'''
            
            focuLength = Q[2][3]
            baseLine = 217.3468
            Z = disparity_to_distance(disp, focuLength, baseLine)
            #cv2.imwrite(os.path.join(i_path, 'distance.png'), Z)
            
            #disp = cv2.pyrUp(cv2.pyrUp(disp))
            '''
            h, w = imgL.shape[:2]
            f = 6761 / 4
            Q = np.float32([[1, 0, 0, -0.5*w],
                          [0,-1, 0,  0.5*h],
                          [0, 0, 0,     -f],
                          [0, 0, 1,      0]])
                          '''
            
            points = cv2.reprojectImageTo3D(disp, Q)
            #mask = disp < 320 * 4 #disp.min()
            #disp2 = disp[np.logical_and(disp > 100, disp % 40 != 0, disp < 320 * 4)]
            mask = [np.logical_and(disp > 132, disp < 320)] # > 120, < 230
            
            mask2 = green_mask(imgL, 3)
            mask3 = mask[0]&mask2
            out_points = points[mask3]
            out_fn = os.path.join(i_path, 'out.ply')
            colors = cv2.cvtColor(imgL, cv2.COLOR_BGR2RGB) #imgL
            out_colors = colors[mask3]
            write_ply(out_fn, out_points, out_colors)
    
    
    return

def generate_meta_height_hist(in_dir, out_dir, calib):
    
    meta, bin_left, bin_right = find_input_files(in_dir)
    if meta == [] or bin_left == [] or bin_right == []:
        return
    
    metadata = lower_keys(load_json(meta))
    plotNum = get_plot_num(metadata)
    if plotNum == 0:
        return
    
    imgSize = [3296, 2472]
    generate_height_hist(metadata, bin_left, bin_right, out_dir, calib, imgSize)
    
    return

def generate_height_hist(metadata, bin_left, bin_right, out_dir, calib, imgSize):
    
    # create left and right image
    left_img = process_image(bin_left, imgSize)
    right_img = process_image(bin_right, imgSize)
    
    # create disparity image
    frames = []
    frames.append(left_img)
    frames.append(right_img)
    newFrame = calib.rectify(frames)
            
    imgL = cv2.pyrDown(cv2.pyrDown( newFrame[0] ))
    imgR = cv2.pyrDown(cv2.pyrDown( newFrame[1] ))
    
    window_size = 9
    min_disp = 1
    num_disp = 321-min_disp
    stereo = cv2.StereoSGBM(minDisparity = min_disp,
        numDisparities = num_disp,
        SADWindowSize = window_size,
        uniquenessRatio = 2,
        speckleWindowSize = 50,
        speckleRange = 3,
        disp12MaxDiff = 3,
        P1 = 8*window_size*window_size,
        P2 = 32*window_size*window_size,
        fullDP = False
    )
        
    print 'computing disparity...'
    disp = stereo.compute(imgL, imgR).astype(np.float32) / 16.0
    # disparity threshold
    mask = [np.logical_and(disp > 132, disp < 320)]
    mask2 = green_mask(imgL, 3)
    mask3 = mask[0]&mask2
    
    # disparity_to_distance
    Q = calib.disp_to_depth_mat
    focuLength = Q[2][3] / 4.0 # shrink twice
    baseLine = 217.3468 # in mm
    center_position = get_position(metadata)
    Z = disparity_to_distance(disp, focuLength, baseLine)
    heightMap = center_position[2]*1000 - Z
    #heightMap = heightMap[mask3]
    
    # calculate a plot number for each pixel, 1728 plots by default
    fov = get_fov(metadata, center_position[2], imgSize)
    convt = terra_common.StereoPixelConverter()
    plotNum, pixelBoundary = convt.getPlotNumForPixel(center_position, fov)
    
    
    # save plant level images
    leaf_mask = np.zeros_like(cv2.cvtColor(imgL, cv2.COLOR_BGR2GRAY))
    disp = (np.rot90(disp))
    cv2.imwrite(os.path.join(out_dir, 'disp.png'), disp)
    for plot, bound in zip(plotNum, pixelBoundary):
        roi_img = disp[:, bound[0]:bound[1]]
        cv2.imwrite(os.path.join(out_dir, str(plot)+'_disp.png'), roi_img)
    
    show_img = cv2.cvtColor(imgL, cv2.COLOR_BGR2RGB)
    leaf_mask[mask2] = 255
    res = cv2.bitwise_and(show_img,show_img,mask = leaf_mask)
    cv2.imwrite(os.path.join(out_dir, 'left.jpg'), np.rot90(res))
    
    export_height_data_to_file(heightMap, out_dir, plotNum, pixelBoundary, mask3)
    
    return


def export_height_data_to_file(heightMap, out_dir, plotNum, pixelBoundary, leaf_mask):
    
    if not os.path.isdir(out_dir):
        return
    
    heightMap = np.rot90(heightMap)
    leaf_mask = np.rot90(leaf_mask)
    #z_shift = 400 - 65
    for plot, bound in zip(plotNum, pixelBoundary):
        roi_map = heightMap[:, bound[0]:bound[1]]
        roi_mask = leaf_mask[:, bound[0]:bound[1]]
        roi_map = roi_map[roi_mask]
    
        zOffset = 8
        zRange = [0, 3200]
        hist = np.zeros(400)
        
        zloop = 0
        for z in range(zRange[0],zRange[1], zOffset):       
            zmin = z
            zmax = (z+zOffset)
            zIndex = np.where((roi_map>zmin) & (roi_map<zmax));
            num = len(zIndex[0])
            hist[zloop] = num
            zloop = zloop + 1
        
        
        #hist_shift = np.concatenate((hist[z_shift:], hist[:z_shift]))
        out_file_name = os.path.join(out_dir, str(plot)+'.npy')
        np.save(out_file_name, hist)
    
    return


def get_plot_num(meta):
    
    center_position, hh = parse_metadata(meta)
    
    convt = terra_common.CoordinateConverter()
    
    plot_row, plot_col = convt.fieldPosition_to_fieldPartition_s2_1728(center_position[0], center_position[1])
    
    plotNum = convt.fieldPartition_to_plotNum_s2_1728(plot_row, plot_col)
    
    return plotNum

def parse_metadata(metadata):
    
    try:
        gantry_meta = metadata['lemnatec_measurement_metadata']['gantry_system_variable_metadata']
        gantry_x = gantry_meta["position x [m]"]
        gantry_y = gantry_meta["position y [m]"]
        gantry_z = gantry_meta["position z [m]"]
        
        capture_time =gantry_meta["time"]
        if len(capture_time) == 19:
            hh = int(capture_time[11:13])
        else:
            hh = 0
        
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
    
    return center_position, hh

ply_header = '''ply
format ascii 1.0
element vertex %(vert_num)d
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
'''

def write_ply(fn, verts, colors):
    verts = verts.reshape(-1, 3)
    colors = colors.reshape(-1, 3)
    verts = np.hstack([verts, colors])
    with open(fn, 'wb') as f:
        f.write((ply_header % dict(vert_num=len(verts))).encode('utf-8'))
        np.savetxt(f, verts, fmt='%f %f %f %d %d %d')
    
    return

def disparity_to_distance(disp, focuLength, baseLine):
    
    Z = (focuLength * baseLine) / disp
    
    return Z

def stereo_calibrate(in_dir, boardSize, squareSize, imgSize, out_dir):
    
    calibrator = calibration.StereoCalibrator(boardSize[0], boardSize[1], squareSize, imgSize)
    list_dirs = os.walk(in_dir)
    for root, dirs, files in list_dirs:
        for d in dirs:
            i_path = os.path.join(in_dir, d)
            if not os.path.isdir(i_path):
                continue
            
            left_file = os.path.join(i_path, 'left.jpg')
            right_file = os.path.join(i_path, 'right.jpg')
            if not os.path.exists(left_file) or not os.path.exists(right_file):
                continue
            
            print(left_file)
            
            left_img = cv2.imread(left_file)
            right_img = cv2.imread(right_file)
            
            #imgL = cv2.pyrDown( left_img )
            #imgR = cv2.pyrDown( right_img )
            
            image_pair = []
            image_pair.append(left_img)
            image_pair.append(right_img)
            try:
                calibrator.add_corners(image_pair, True)
                #print("add success!")
            except Exception as ex:
                print left_file + ' ' + str(ex)
                
            
            
    calibration_data = calibrator.calibrate_cameras()
    avg_error = calibrator.check_calibration(calibration_data)
    print avg_error
    calibration_data.export(out_dir)
    
    
    
    return

def StereoCalib(in_dir, boardSize, squareSize, img_size, out_dir):
    
    if not os.path.isdir(in_dir):
        return None
    # obtain pair corner coordinate
    corner_list = []
    list_dirs = os.walk(in_dir)
    
    object_point = []
    corner_coordinates = np.zeros((np.prod(boardSize), 3), np.float32)
    corner_coordinates[:, :2] = np.indices(boardSize).T.reshape(-1, 2)
    corner_coordinates *= squareSize
    
    image_points_left = []
    image_points_right = []
    img_count = 0
    
    for root, dirs, files in list_dirs:
        for d in dirs:
            i_path = os.path.join(in_dir, d)
            if not os.path.isdir(i_path):
                continue
            
            left_file = os.path.join(i_path, 'left.jpg')
            right_file = os.path.join(i_path, 'right.jpg')
            if not os.path.exists(left_file) or not os.path.exists(right_file):
                continue
            
            print(left_file)
            
            left_img = cv2.cvtColor(cv2.imread(left_file), cv2.COLOR_BGR2GRAY)
            right_img = cv2.cvtColor(cv2.imread(right_file), cv2.COLOR_BGR2GRAY)
            
            
            left_ret, left_corners = cv2.findChessboardCorners(left_img, boardSize)
            if not left_ret:
                continue
            right_ret, right_corners = cv2.findChessboardCorners(right_img, boardSize)
            if not right_ret:
                continue
            
            cv2.cornerSubPix(left_img, left_corners, (11,11), (-1,-1), (cv2.TERM_CRITERIA_MAX_ITER+cv2.TERM_CRITERIA_EPS, 30, 0.01))
            cv2.cornerSubPix(right_img, right_corners, (11,11), (-1,-1), (cv2.TERM_CRITERIA_MAX_ITER+cv2.TERM_CRITERIA_EPS, 30, 0.01))
            corner_list.append(left_corners)
            corner_list.append(right_corners)
            object_point.append(corner_coordinates)
            image_points_left.append(left_corners.reshape(-1, 2))
            image_points_right.append(right_corners.reshape(-1, 2))
            img_count += 2
            print("success!")
    
    # run stereo calibration
    (retval, cameraMatrix1, 
    distCoeffs1, cameraMatrix2, distCoeffs2,
     R, T, E, F) = cv2.stereoCalibrate(object_point,
                                       image_points_left,
                                       image_points_right,
                                       None,
                                       None,
                                       None,
                                       None,
                                       img_size,
                                       None,
                                       None,
                                       None,
                                       None,
                                       criteria = (cv2.TERM_CRITERIA_MAX_ITER+cv2.TERM_CRITERIA_EPS, 100, 1e-5),
                                       flags = (cv2.CALIB_USE_INTRINSIC_GUESS+cv2.CALIB_FIX_ASPECT_RATIO
                                                +cv2.CALIB_FIX_PRINCIPAL_POINT+cv2.CALIB_ZERO_TANGENT_DIST)
                                       )
    
    # calibration quality check
    check_calibration(image_points_left, image_points_right, cameraMatrix1, cameraMatrix2, distCoeffs1, distCoeffs2, F, object_point, img_count)
    
    # save parameters
    
    
    return

def export_matrices(out_dir):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    return

def green_mask(img, kernelSize):
    
    #im = Image.fromarray(img)
    
    #r, g, b = im.split()
    
    r = img[:,:,0]
    g = img[:,:,1]
    b = img[:,:,2]
    
    sub_img = (g.astype('int') - r.astype('int') + 2) > 0 # normal: -2
    
    mask = np.zeros_like(b)
    
    mask[sub_img] = 255
    
    im = Image.fromarray(mask)
    blur = im.filter(ImageFilter.BLUR)
    pix = np.array(blur)
    #blur = cv2.blur(mask,(kernelSize,kernelSize))
    
    #pix = cv2.pyrDown(cv2.pyrDown( pix ))
    sub_mask = pix > 128
    
    return sub_mask

def find_input_files(in_dir):
    
    json_suffix = os.path.join(in_dir, '*_metadata.json')
    jsons = glob(json_suffix)
    if len(jsons) == 0:
        terra_common.fail('Could not find .json file')
        return [], [], []
        
        
    left_suffix = os.path.join(in_dir, '*left.bin')
    left_bins = glob(left_suffix)
    if len(left_bins) == 0:
        terra_common.fail('Could not find .bin file')
        return [], [], []
    
    right_suffix = os.path.join(in_dir, '*right.bin')
    right_bins = glob(right_suffix)
    if len(right_bins) == 0:
        terra_common.fail('Could not find .bin file')
        return [], [], []
    
    return jsons[0], left_bins[0], right_bins[0]

def check_calibration(image_points_left, image_points_right, left_camMat, right_camMat, leftDistC, rightDistC, F, object_point, img_count):
    
    sides = "left", "right"
    which_image = {sides[0]:1, sides[1]:2}
    undistorted, lines = {}, {}
    
    
    undistorted["left"] = cv2.undistortPoints(
                        np.concatenate(image_points_left).reshape(-1,1,2),
                        left_camMat, leftDistC, P=left_camMat)
    lines["left"] = cv2.computeCorrespondEpilines(undistorted["left"], which_image["left"], F)
    
    undistorted["right"] = cv2.undistortPoints(
                        np.concatenate(image_points_right).reshape(-1,1,2),
                        right_camMat, leftDistC, P=right_camMat)
    lines["right"] = cv2.computeCorrespondEpilines(undistorted["right"], which_image["right"], F)
    
    total_error = 0
    this_side, other_side = sides
    for side in sides:
        for i in range(len(undistorted[side])):
            total_error += abs(undistorted[this_side][i][0][0] *
                               lines[other_side][i][0][0] +
                               undistorted[this_side][i][0][1] *
                               lines[other_side][i][0][1] +
                               lines[other_side][i][0][2])
        other_side, this_side = sides
    total_points = img_count*len(object_point)
    return total_error/total_points

def get_position(metadata):
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
            cam_z = 0.578
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
        cam_meta = metadata['lemnatec_measurement_metadata']['sensor_fixed_metadata']
        fov = cam_meta["field of view at 2m in x- y- direction [m]"]
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

def process_image(im_path, shape):
    im = np.fromfile(im_path, dtype='uint8').reshape(shape[::-1])
    im_color = demosaic(im)
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

if __name__ == '__main__':
    main()
