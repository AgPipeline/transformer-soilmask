import os
import cv2
import numpy as np
from osgeo import gdal
from PIL import Image
from skimage import morphology

from pyclowder.utils import CheckMessage
from pyclowder.datasets import download_metadata, upload_metadata, remove_metadata
from terrautils.metadata import get_extractor_metadata, get_terraref_metadata, \
    get_season_and_experiment
from terrautils.extractors import TerrarefExtractor, is_latest_file, check_file_in_dataset, load_json_file, \
    build_metadata, build_dataset_hierarchy_crawl, upload_to_dataset, file_exists, contains_required_files
from terrautils.formats import create_geotiff, create_image, compress_geotiff
from terrautils.spatial import geojson_to_tuples, geojson_to_tuples_betydb


SATURATE_THRESHOLD = 245
MAX_PIXEL_VAL = 255
SMALL_AREA_THRESHOLD = 200

def getImageQuality(imgfile):
    img = Image.open(imgfile)
    img = np.array(img)

    NRMAC = MAC(img, img, img)

    return NRMAC

def gen_plant_mask(colorImg, kernelSize=3):
    r = colorImg[:, :, 2]
    g = colorImg[:, :, 1]
    b = colorImg[:, :, 0]

    sub_img = (g.astype('int') - r.astype('int') - 0) > 0  # normal: -2

    mask = np.zeros_like(b)

    mask[sub_img] = MAX_PIXEL_VAL

    blur = cv2.blur(mask, (kernelSize, kernelSize))
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

def saturated_pixel_classification(gray_img, baseMask, saturatedMask, dilateSize=0):
    # add saturated area into basic mask
    saturatedMask = morphology.binary_dilation(saturatedMask, morphology.diamond(dilateSize))

    rel_img = np.zeros_like(gray_img)
    rel_img[saturatedMask] = MAX_PIXEL_VAL

    label_img, num = morphology.label(rel_img, connectivity=2, return_num=True)

    rel_mask = baseMask

    for i in range(1, num):
        x = (label_img == i)

        if np.sum(x) > 100000:  # if the area is too large, do not add it into basic mask
            continue

        if not (x & baseMask).any():
            continue

        rel_mask = rel_mask | x

    return rel_mask

def over_saturation_pocess(rgb_img, init_mask, threshold=SATURATE_THRESHOLD):
    # connected component analysis for over saturation pixels
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

def gen_saturated_mask(img, kernelSize):
    binMask = gen_plant_mask(img, kernelSize)
    binMask = remove_small_area_mask(binMask,
                                     500)  # 500 is a parameter for number of pixels to be removed as small area
    binMask = remove_small_holes_mask(binMask,
                                      300)  # 300 is a parameter for number of pixels to be filled as small holes

    binMask = over_saturation_pocess(img, binMask, SATURATE_THRESHOLD)

    binMask = remove_small_holes_mask(binMask, 4000)

    return binMask

def gen_mask(img, kernelSize):
    binMask = gen_plant_mask(img, kernelSize)
    binMask = remove_small_area_mask(binMask, SMALL_AREA_THRESHOLD)
    binMask = remove_small_holes_mask(binMask,
                                      3000)  # 3000 is a parameter for number of pixels to be filled as small holes

    return binMask

def gen_rgb_mask(img, binMask):
    rgbMask = cv2.bitwise_and(img, img, mask=binMask)

    return rgbMask

def rgb2gray(rgb):
    r, g, b = rgb[:,:,0], rgb[:,:,1], rgb[:,:,2]
    gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
    return gray

def MAC(im1, im2, im):  # main function: Multiscale Autocorrelation (MAC)
    h, v, c = im1.shape
    if c > 1:
        im = np.matrix.round(rgb2gray(im))
        im1 = np.matrix.round(rgb2gray(im1))
        im2 = np.matrix.round(rgb2gray(im2))
    # multiscale parameters
    scales = np.array([2, 3, 5])
    FM = np.zeros(len(scales))
    for s in range(len(scales)):
        im1[0: h - 1, :] = im[1:h, :]
        im2[0: h - scales[s], :] = im[scales[s]:h, :]
        dif = im * (im1 - im2)
        FM[s] = np.mean(dif)
    NRMAC = np.mean(FM)
    return NRMAC

def check_saturation(img):
    # check how many percent of pix close to 255 or 0
    grayImg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    m1 = grayImg > SATURATE_THRESHOLD
    m2 = grayImg < 20  # 20 is a threshold to classify low pixel value

    over_rate = float(np.sum(m1)) / float(grayImg.size)
    low_rate = float(np.sum(m2)) / float(grayImg.size)

    return over_rate, low_rate

def check_brightness(img):
    # gen average pixel value from grayscale image
    grayImg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    aveValue = np.average(grayImg)

    return aveValue

def gen_cc_enhanced(input_path, kernelSize=3):
    # abandon low quality images, mask enhanced
    # TODO: cv2 has problems with some RGB geotiffs...
    # img = cv2.imread(input_path)
    img = np.rollaxis(gdal.Open(input_path).ReadAsArray().astype(np.uint8), 0, 3)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # calculate image scores
    over_rate, low_rate = check_saturation(img)

    # TODO: disabling this check for now because it's crashing extractor - generate mask regardless
    # if low score, return None
    # low_rate is percentage of low value pixels(lower than 20) in the grayscale image, if low_rate > 0.1, return
    # aveValue is average pixel value of grayscale image, if aveValue lower than 30 or higher than 195, return
    # quality_score is a score from Multiscale Autocorrelation (MAC), if quality_score lower than 13, return

    #aveValue = check_brightness(img)
    #quality_score = getImageQuality(input_path)
    #if low_rate > 0.1 or aveValue < 30 or aveValue > 195 or quality_score < 13:
    #    return None, None, None

    # saturated image process
    # over_rate is percentage of high value pixels(higher than SATUTATE_THRESHOLD) in the grayscale image, if over_rate > 0.15, try to fix it use gen_saturated_mask()
    if over_rate > 0.15:
        binMask = gen_saturated_mask(img, kernelSize)
    else:  # nomal image process
        binMask = gen_mask(img, kernelSize)

    c = np.count_nonzero(binMask)
    ratio = c / float(binMask.size)

    rgbMask = gen_rgb_mask(img, binMask)

    return ratio, rgbMask


def add_local_arguments(parser):
    # add any additional arguments to parser
    parser.add_argument('--left', type=bool, default=os.getenv('LEFT_ONLY', True),
                        help="only generate a mask for the left image")

class rgbEnhancementExtractor(TerrarefExtractor):

    def __init__(self):
        super(rgbEnhancementExtractor, self).__init__()

        add_local_arguments(self.parser)

        # parse command line and load default logging configuration
        self.setup(sensor='rgb_mask')

        # assign local arguments
        self.leftonly = self.args.left

    def check_message(self, connector, host, secret_key, resource, parameters):
        if "rulechecked" in parameters and parameters["rulechecked"]:
            return CheckMessage.download

        self.start_check(resource)

        if not is_latest_file(resource):
            self.log_skip(resource, "not latest file")
            return CheckMessage.ignore

        # Check for a left and right TIF file - skip if not found
        if not contains_required_files(resource, ['_left.tif', '_right.tif']):
            self.log_skip(resource, "missing required files")
            return CheckMessage.ignore

        # Check metadata to verify we have what we need
        md = download_metadata(connector, host, secret_key, resource['id'])
        if get_terraref_metadata(md):
            if get_extractor_metadata(md, self.extractor_info['name'], self.extractor_info['version']):
                # Make sure outputs properly exist
                timestamp = resource['dataset_info']['name'].split(" - ")[1]
                left_mask_tiff = self.sensors.create_sensor_path(timestamp, opts=['left'])
                right_mask_tiff = self.sensors.create_sensor_path(timestamp, opts=['right'])
                if (self.leftonly and file_exists(left_mask_tiff)) or (
                            not self.leftonly and file_exists(left_mask_tiff) and file_exists(right_mask_tiff)):
                    self.log_skip(resource, "metadata v%s and outputs already exist" % self.extractor_info['version'])
                    return CheckMessage.ignore
            # Have TERRA-REF metadata, but not any from this extractor
            return CheckMessage.download
        else:
            self.log_skip(resource, "no terraref metadata found")
            return CheckMessage.ignore

    def process_message(self, connector, host, secret_key, resource, parameters):
        self.start_message(resource)

        # Get left/right files and metadata
        img_left, img_right, metadata = None, None, None
        for fname in resource['local_paths']:
            if fname.endswith('_dataset_metadata.json'):
                all_dsmd = load_json_file(fname)
                terra_md_full = get_terraref_metadata(all_dsmd, 'stereoTop')
            elif fname.endswith('_left.tif'):
                img_left = fname
            elif fname.endswith('_right.tif'):
                img_right = fname
        if None in [img_left, img_right, terra_md_full]:
            raise ValueError("could not locate all files & metadata in processing")

        timestamp = resource['dataset_info']['name'].split(" - ")[1]
        target_dsid = resource['id']

        left_rgb_mask_tiff = self.sensors.create_sensor_path(timestamp, opts=['left'])
        right_rgb_mask_tiff = self.sensors.create_sensor_path(timestamp, opts=['right'])
        uploaded_file_ids = []
        right_ratio, left_ratio = 0, 0

        left_bounds = geojson_to_tuples(terra_md_full['spatial_metadata']['left']['bounding_box'])
        right_bounds = geojson_to_tuples(terra_md_full['spatial_metadata']['right']['bounding_box'])

        if not file_exists(left_rgb_mask_tiff) or self.overwrite:
            self.log_info(resource, "creating %s" % left_rgb_mask_tiff)

            left_ratio, left_rgb = gen_cc_enhanced(img_left)
            # Bands must be reordered to avoid swapping R and B
            left_rgb = cv2.cvtColor(left_rgb, cv2.COLOR_BGR2RGB)

            create_geotiff(left_rgb, left_bounds, left_rgb_mask_tiff, None, False, self.extractor_info, terra_md_full)
            compress_geotiff(left_rgb_mask_tiff)
            self.created += 1
            self.bytes += os.path.getsize(left_rgb_mask_tiff)

        found_in_dest = check_file_in_dataset(connector, host, secret_key, target_dsid, left_rgb_mask_tiff,
                                              remove=self.overwrite)
        if not found_in_dest:
            self.log_info(resource, "uploading %s" % left_rgb_mask_tiff)
            fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid,
                                       left_rgb_mask_tiff)
            uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)


        if not self.leftonly:
            if not file_exists(right_rgb_mask_tiff) or self.overwrite:


                right_ratio, right_rgb = gen_cc_enhanced(img_right)

                create_geotiff(right_rgb, right_bounds, right_rgb_mask_tiff, None, False, self.extractor_info, terra_md_full)
                compress_geotiff(right_rgb_mask_tiff)
                self.created += 1
                self.bytes += os.path.getsize(right_rgb_mask_tiff)

            found_in_dest = check_file_in_dataset(connector, host, secret_key, target_dsid, right_rgb_mask_tiff,
                                                  remove=self.overwrite)
            if not found_in_dest:
                self.log_info(resource, "uploading %s" % right_rgb_mask_tiff)
                fileid = upload_to_dataset(connector, host, self.clowder_user, self.clowder_pass, target_dsid,
                                           right_rgb_mask_tiff)
                uploaded_file_ids.append(host + ("" if host.endswith("/") else "/") + "files/" + fileid)


        # Tell Clowder this is completed so subsequent file updates don't daisy-chain
        md = {
            "files_created": uploaded_file_ids,
            "left_mask_ratio": left_ratio
        }
        if not self.leftonly:
            md["right_mask_ratio"] = right_ratio
        extractor_md = build_metadata(host, self.extractor_info, target_dsid, md, 'dataset')
        self.log_info(resource, "uploading extractor metadata to Lv1 dataset")
        remove_metadata(connector, host, secret_key, resource['id'], self.extractor_info['name'])
        upload_metadata(connector, host, secret_key, resource['id'], extractor_md)

        self.end_message(resource)


if __name__ == "__main__":
    extractor = rgbEnhancementExtractor()
    extractor.start()
