#!/usr/bin/env python3
"""Python script for comparing two images they way we want them to be
"""

import argparse
import PIL.Image
import numpy as np


def _get_params() -> tuple:
    """Get the paths to the files
    Returns:
        A tuple containing the two paths
    """
    parser = argparse.ArgumentParser(description='Compares two image files by size and pixel value')

    parser.add_argument('first_file', type=argparse.FileType('r'), help='The first image file to compare')
    parser.add_argument('second_file', type=argparse.FileType('r'), help='The second image file to compare')

    args = parser.parse_args()

    return args.first_file.name, args.second_file.name


def check_images(first_path: str, second_path: str) -> None:
    """Compares the two image files and throws an exception if they don't match
    Arguments:
        first_path: the path to the first file to compare
        second_path: the path to the second file to compare
    """
    first_pixels = PIL.Image.open(first_path)
    first_array = np.array(first_pixels)
    del first_pixels

    second_pixels = PIL.Image.open(second_path)
    second_array = np.array(second_pixels)
    del second_pixels

    if first_array.shape != second_array.shape:
        raise RuntimeError("Image dimensions are different: %s vs %s" % (str(first_array.shape), str(second_array.shape)))

    for i in range(0, first_array.shape[0]):
        for j in range(0, first_array.shape[1]):
            for k in range(0, first_array.shape[2]):
                if first_array[i][j][k] - second_array[i][j][k] != 0:
                    raise RuntimeError("Image pixels are different. First difference at %s %s %s" % (str(i), str(j), str(k)))


if __name__ == '__main__':
    path1, path2 = _get_params()
    check_images(path1, path2)
