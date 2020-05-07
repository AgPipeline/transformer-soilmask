import pathlib

import numpy as np
import cv2

MAX_PIXEL_VAL = 255


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


def load_image(image_path: pathlib.Path) -> np.ndarray:
    img_raw = cv2.imread(str(image_path))
    color_img = cv2.cvtColor(img_raw, cv2.COLOR_BGR2RGB)
    return color_img


def save_mask(output_path: pathlib.Path, bin_mask: np.ndarray):
    np.savez_compressed(output_path, [bin_mask])
