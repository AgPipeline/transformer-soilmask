#!/usr/bin/env python3
"""Tests soilmask.py
"""
import os
import re
import json
import subprocess
import numpy as np
import PIL.Image
from osgeo import gdal

# The name of the source file to test and it's path
SOURCE_FILE = 'soilmask.py'
SOURCE_PATH = os.path.abspath(os.path.join('.', SOURCE_FILE))

# Path relative to the current folder where the testing JSON file are
TESTING_FILE_PATH = os.path.realpath('./test_data')

# Translations for returned metadata keys to expected keys
METADATA_KEY_TRANSLATION = {
    'transformer_name': 'name',
    'transformer_version': 'version',
    'transformer_author': 'author',
    'transformer_description': 'description',
    'transformer_repo': 'repository'
}


def test_exists():
    """Asserts that the source file is available"""
    assert os.path.isfile(SOURCE_PATH)


def test_usage():
    """Program prints a "usage" statement when requested"""
    for flag in ['-h', '--help']:
        ret_val, out = subprocess.getstatusoutput(f'{SOURCE_PATH} {flag}')
        assert re.match('usage', out, re.IGNORECASE)
        assert ret_val == 0


def test_prepare_metadata_for_geotiff():
    """Test metadata preparation"""
    # pylint: disable=import-outside-toplevel
    import soilmask as sm

    data_file_name = os.path.realpath(os.path.join(TESTING_FILE_PATH, 'prepare_metadata_for_geotiff.json'))
    assert os.path.exists(data_file_name)

    with open(data_file_name, 'r', encoding='utf-8') as in_file:
        test_data = json.load(in_file)
        test_data.append(None)
        for test in test_data:
            metadata = sm.__internal__.prepare_metadata_for_geotiff(test)
            assert metadata is not None
            assert isinstance(metadata, dict)
            if test is None:
                continue
            for key, value in metadata.items():
                if METADATA_KEY_TRANSLATION[key] in test:
                    if key not in ['transformer_repo']:
                        assert value == test[METADATA_KEY_TRANSLATION[key]]
                        continue
                    if key == 'transformer_repo':
                        # Special handling
                        if len(value) == 0 and isinstance(value, str):
                            assert (METADATA_KEY_TRANSLATION['transformer_repo'] not in test) or \
                                   (not test[METADATA_KEY_TRANSLATION['transformer_repo']]) or \
                                   ('repUrl' not in test[METADATA_KEY_TRANSLATION['transformer_repo']])
                        else:
                            assert value == str(test[METADATA_KEY_TRANSLATION['transformer_repo']]['repUrl'])


def test_simple_line():
    """Runs the command line and tests the result"""
    orthomosaic_mask_name = 'orthomosaic_mask.tif'
    result_name = 'result.json'
    source_image = os.path.join(TESTING_FILE_PATH, 'orthomosaic.tif')
    source_metadata = os.path.join(TESTING_FILE_PATH, 'experiment.yaml')
    assert os.path.exists(source_image)
    assert os.path.exists(source_metadata)

    working_space = os.path.realpath('./test_results')
    os.makedirs(working_space, exist_ok=True)

    command_line = [SOURCE_PATH, '--metadata', source_metadata, '--working_space', working_space, source_image]
    subprocess.run(command_line, check=True)

    # Check that the expected files were created
    for expected_file in [result_name, orthomosaic_mask_name]:
        assert os.path.exists(os.path.join(working_space, expected_file))

    # Inspect the created files
    with open(os.path.join(working_space, result_name), encoding='utf-8') as in_file:
        res = json.load(in_file)
        assert 'code' in res
        assert res['code'] == 0

    img = gdal.Open(os.path.join(working_space, orthomosaic_mask_name)).ReadAsArray()
    assert img is not None
    assert isinstance(img, np.ndarray)


def test_outputfile_command_line():
    """Runs the command line and tests the result"""
    orthomosaic_mask_name = 'soilmask.tif'
    result_name = 'result.json'
    source_image = os.path.join(TESTING_FILE_PATH, 'orthomosaic.tif')
    source_metadata = os.path.join(TESTING_FILE_PATH, 'experiment.yaml')
    assert os.path.exists(source_image)
    assert os.path.exists(source_metadata)

    working_space = os.path.realpath('./test_results')
    os.makedirs(working_space, exist_ok=True)

    command_line = [SOURCE_PATH, '--metadata', source_metadata, '--working_space', working_space,
                    '--out_file', orthomosaic_mask_name, source_image]
    subprocess.run(command_line, check=True)

    # Check that the expected files were created
    for expected_file in [result_name, orthomosaic_mask_name]:
        assert os.path.exists(os.path.join(working_space, expected_file))

    # Inspect the created files
    with open(os.path.join(working_space, result_name), encoding='utf-8') as in_file:
        res = json.load(in_file)
        assert 'code' in res
        assert res['code'] == 0

    img = gdal.Open(os.path.join(working_space, orthomosaic_mask_name)).ReadAsArray()
    assert img is not None
    assert isinstance(img, np.ndarray)


def test_plain_tiff():
    """Runs the command line for a non-GeoTiff file and tests the result"""
    orthomosaic_mask_name = 'plain_mask.tif'
    result_name = 'result.json'
    source_image = os.path.join(TESTING_FILE_PATH, 'orthomosaic.tif')
    source_metadata = os.path.join(TESTING_FILE_PATH, 'experiment.yaml')
    assert os.path.exists(source_image)
    assert os.path.exists(source_metadata)

    # Create a non-georeferenced tiff image from the source image
    plain_tiff_image = os.path.join(TESTING_FILE_PATH, 'plain.tif')
    if os.path.exists(plain_tiff_image):
        os.unlink(plain_tiff_image)
    img = PIL.Image.open(source_image)
    img_array = np.array(img)
    result = PIL.Image.fromarray(img_array)
    result.save(plain_tiff_image)

    # Setup parameters for running the test
    working_space = os.path.realpath('./test_results')
    os.makedirs(working_space, exist_ok=True)
    for expected_file in [result_name, orthomosaic_mask_name]:
        cur_path = os.path.join(working_space, expected_file)
        if os.path.exists(cur_path):
            os.unlink(cur_path)

    command_line = [SOURCE_PATH, '--metadata', source_metadata, '--working_space', working_space, plain_tiff_image]
    subprocess.run(command_line, check=True)

    # Check that the expected files were created
    for expected_file in [result_name, orthomosaic_mask_name]:
        assert os.path.exists(os.path.join(working_space, expected_file))

    # Inspect the created files
    with open(os.path.join(working_space, result_name), encoding='utf-8') as in_file:
        res = json.load(in_file)
        assert 'code' in res
        assert res['code'] == 0

    img = gdal.Open(os.path.join(working_space, orthomosaic_mask_name)).ReadAsArray()
    assert img is not None
    assert isinstance(img, np.ndarray)
