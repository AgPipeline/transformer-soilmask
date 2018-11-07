'''
Created on Sep 17, 2018

@author: zli
'''

import cv2
import time
import os, sys, copy
from options.test_options import TestOptions
from models.models import create_model
import numpy as np
from PIL import Image
import torchvision.transforms as transforms
from skimage import morphology

transform_list = [transforms.ToTensor(),
                  transforms.Normalize((0.5, 0.5, 0.5),(0.5, 0.5, 0.5)),
                ]
transform = transforms.Compose(transform_list)

SATUTATE_THRESHOLD = 245
MAX_PIXEL_VAL = 255
SMALL_AREA_THRESHOLD = 200

# model initial
def init_model():
    
    opt = test_option()
    model = create_model(opt)
    
    return model

class test_option:
        dataroot = ''
        batchSize = 1
        loadSize = 256
        fineSize = 256
        input_nc = 3
        output_nc = 3
        ngf = 64
        ndf = 64
        which_model_netD = 'basic'
        which_model_netG = 'unet_256'
        n_layers_D = 3
        gpu_ids = [0]
        name = 'terra_color_to_color_DL1_0.8'
        dataset_mode = 'aligned'
        model = 'pix2pix'
        which_direction = 'AtoB'
        nThreads = 1
        checkpoints_dir = './checkpoints'
        norm = 'batch'
        which_epoch = '4'
        serial_batches = True
        no_flip = True
        isTrain = False
        no_dropout = True
        max_dataset_size = float("inf")
        resize_or_crop = 'resize_or_crop'
        

# input image size: 256*256
def core_gan_process(input_img_data, image_path, model):
    
    data = input_transform(input_img_data, image_path)
    
    model.set_input(data)
    model.test()
    visuals = model.get_current_visuals()
    
    rel = visuals['fake_B']
    
    open_cv_image = rel[:, :, ::-1].copy()
    
    return open_cv_image

def input_transform(src_data, image_path):
    
    w = 256
    AB_pix = np.zeros((w, w*2, 3))
    AB_pix[:,:w] = src_data
    AB_pix[:,w:] = src_data
    AB_pix = cv2.cvtColor(np.uint8(AB_pix), cv2.COLOR_BGR2RGB)
    AB = Image.fromarray(np.uint8(AB_pix))
    #AB.show()
    AB = transform(AB)
    
    A = AB[:, :, :w]
  
    return {'A': A, 'B': A,
            'A_paths': image_path, 'B_paths': image_path}
    
def gan_enhance_process(input_path, model):
    
    input_img_size = 256
    
    img = cv2.imread(input_path)
    resize_img = cv2.resize(img, (input_img_size*2, input_img_size*3))
    resize_color = np.uint8(np.zeros((resize_img.shape)))
    b = resize_color[:,:,0]
    resize_bin = np.zeros_like(b)
    
    for i in range(3):
        for j in range(2):
            cropped_img = resize_img[i*input_img_size:(i+1)*input_img_size, j*input_img_size:(j+1)*input_img_size]
            roi_img = core_gan_process(cropped_img, input_path, model)
            bin_img = gen_plant_mask(roi_img, 5)
            resize_color[i*input_img_size:(i+1)*input_img_size, j*input_img_size:(j+1)*input_img_size] = roi_img
            resize_bin[i*input_img_size:(i+1)*input_img_size, j*input_img_size:(j+1)*input_img_size] = bin_img
    
    rel_color = cv2.resize(resize_color, (img.shape[1], img.shape[0]))
    rel_bin = cv2.resize(resize_bin, (img.shape[1], img.shape[0]))
    
    return rel_color, rel_bin

def gen_plant_mask(colorImg, kernelSize=3):
    
    r = colorImg[:,:,2]
    g = colorImg[:,:,1]
    b = colorImg[:,:,0]
    
    sub_img = (g.astype('int') - r.astype('int') -0) > 0 # normal: -2
    
    mask = np.zeros_like(b)
    
    mask[sub_img] = MAX_PIXEL_VAL
    
    blur = cv2.blur(mask,(kernelSize,kernelSize))
    pix = np.array(blur)
    sub_mask = pix > 128
    
    mask_1 = np.zeros_like(b)
    mask_1[sub_mask] = MAX_PIXEL_VAL
    
    return mask_1

def remove_small_area_mask(maskImg, min_area_size):
    
    mask_array = maskImg > 0
    rel_array = morphology.remove_small_objects(mask_array, min_area_size)
    
    rel_img = np.zeros_like(maskImg)
    rel_img[rel_array] = MAX_PIXEL_VAL
    
    return rel_img

def remove_small_holes_mask(maskImg, max_hole_size):
    
    mask_array = maskImg > 0
    rel_array = morphology.remove_small_holes(mask_array, max_hole_size)
    rel_img = np.zeros_like(maskImg)
    rel_img[rel_array] = MAX_PIXEL_VAL
    
    return rel_img

# connected component analysis for over saturation pixels
def over_saturation_pocess(rgb_img, init_mask, threshold = SATUTATE_THRESHOLD):
    
    gray_img = cv2.cvtColor(rgb_img, cv2.COLOR_BGR2GRAY)
    
    mask_over = gray_img > threshold
    
    mask_0 = gray_img < threshold
    
    src_mask_array = init_mask > 0
    
    mask_1 = src_mask_array & mask_0
    
    mask_1 = morphology.remove_small_objects(mask_1, SMALL_AREA_THRESHOLD)
    
    mask_over = morphology.remove_small_objects(mask_over, SMALL_AREA_THRESHOLD)
    
    rel_mask = saturated_pixel_classification(gray_img, mask_1, mask_over, 1)
    rel_img = np.zeros_like(gray_img)
    rel_img[rel_mask] = MAX_PIXEL_VAL
    
    return rel_img


# add saturated area into basic mask
def saturated_pixel_classification(gray_img, baseMask, saturatedMask, dilateSize=0):
    
    saturatedMask = morphology.binary_dilation(saturatedMask, morphology.diamond(dilateSize))
    
    rel_img = np.zeros_like(gray_img)
    rel_img[saturatedMask] = MAX_PIXEL_VAL
    
    label_img, num = morphology.label(rel_img, connectivity=2, return_num=True)
    
    rel_mask = baseMask
    
    for i in range(1, num):
        x = (label_img == i)
        
        if np.sum(x) > 100000: # if the area is too large, do not add it into basic mask
            continue
        
        if not (x & baseMask).any():
            continue
        
        rel_mask = rel_mask | x
    
    return rel_mask
    

# check how many percent of pix close to 255 or 0
def check_saturation(img):
    
    grayImg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    m1 = grayImg > SATUTATE_THRESHOLD
    m2 = grayImg < 20 # 20 is a threshold to classify low pixel value
    
    over_rate = float(np.sum(m1))/float(grayImg.size)
    low_rate = float(np.sum(m2))/float(grayImg.size)
    
    return over_rate, low_rate

# gen average pixel value from grayscale image
def check_brightness(img):
    
    grayImg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    aveValue = np.average(grayImg)
    
    return aveValue

def getImageQuality(imgfile):
    
    img = Image.open(imgfile)
    img = np.array(img)

    NRMAC = MAC(img, img, img)

    return NRMAC

def MAC(im1,im2, im): # main function: Multiscale Autocorrelation (MAC)
    h, v, c = im1.shape
    if c>1:
        im  = np.matrix.round(rgb2gray(im))
        im1 = np.matrix.round(rgb2gray(im1))
        im2 = np.matrix.round(rgb2gray(im2))
    # multiscale parameters
    scales = np.array([2, 3, 5])
    FM = np.zeros(len(scales))
    for s in range(len(scales)):
        im1[0: h-1,:] = im[1:h,:]
        im2[0: h-scales[s], :]= im[scales[s]:h,:]
        dif = im*(im1 - im2)
        FM[s] = np.mean(dif)
    NRMAC = np.mean(FM)
    return NRMAC

def rgb2gray(rgb):
    r, g, b = rgb[:,:,0], rgb[:,:,1], rgb[:,:,2]
    gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
    return gray

def gen_saturated_mask(img, kernelSize):
    
    binMask = gen_plant_mask(img, kernelSize)
    binMask = remove_small_area_mask(binMask, 500)  # 500 is a parameter for number of pixels to be removed as small area 
    binMask = remove_small_holes_mask(binMask, 300) # 300 is a parameter for number of pixels to be filled as small holes
    
    binMask = over_saturation_pocess(img, binMask, SATUTATE_THRESHOLD)
    
    binMask = remove_small_holes_mask(binMask, 4000) 
    
    return binMask

def gen_mask(img, kernelSize):
    
    binMask = gen_plant_mask(img, kernelSize)
    binMask = remove_small_area_mask(binMask, SMALL_AREA_THRESHOLD)
    binMask = remove_small_holes_mask(binMask, 3000) # 3000 is a parameter for number of pixels to be filled as small holes
    
    return binMask

def gen_rgb_mask(img, binMask):
    
    rgbMask = cv2.bitwise_and(img, img, mask = binMask)
    
    return rgbMask


# abandon low quality images, mask enhanced
def gen_cc_enhanced(input_path, kernelSize=3):
    
    img = cv2.imread(input_path)
    
    # calculate image scores
    over_rate, low_rate = check_saturation(img)
    
    aveValue = check_brightness(img)
    
    quality_score = getImageQuality(input_path)
    
    # if low score, return None
    # low_rate is percentage of low value pixels(lower than 20) in the grayscale image, if low_rate > 0.1, return
    # aveValue is average pixel value of grayscale image, if aveValue lower than 30 or higher than 195, return
    # quality_score is a score from Multiscale Autocorrelation (MAC), if quality_score lower than 13, return
    if low_rate > 0.1 or aveValue < 30 or aveValue > 195 or quality_score < 13:
        return None, None, None
    
    # saturated image process
    # over_rate is percentage of high value pixels(higher than SATUTATE_THRESHOLD) in the grayscale image, if over_rate > 0.15, try to fix it use gen_saturated_mask()
    if over_rate > 0.15:
        binMask = gen_saturated_mask(img, kernelSize)
    else:   # nomal image process
        binMask = gen_mask(img, kernelSize)
        
    c = np.count_nonzero(binMask)
    ratio = c/float(binMask.size)
    
    rgbMask = gen_rgb_mask(img, binMask)
    
    return ratio, binMask, rgbMask

def main():
    
    input_path = '/data/Terra/ua-mac/Level_1/stereoTop/2018-10-31/2017-05-26__15-20-56-470_plot_0.jpg'
    
    #model = init_model()
    #rel_color, rel_bin = gan_enhance_process(input_path, model)
    
    ratio, binMask, rgbMask = gen_cc_enhanced(input_path)
    

    return

if __name__ == "__main__":

    main()
    