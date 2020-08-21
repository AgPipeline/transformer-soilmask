#!/usr/bin/env python3
"""Tests soilmask.py
"""
import os
import re
import json
import subprocess
import numpy as np
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

    with open(data_file_name, 'r') as in_file:
        test_data = json.load(in_file)
        test_data.append(None)
        for test in test_data:
            md = sm.__internal__.prepare_metadata_for_geotiff(test)
            assert md is not None
            assert isinstance(md, dict)
            if test is None:
                continue
            for key, value in md.items():
                if key in test:
                    if key not in ['transformer_repo']:
                        assert value == test[METADATA_KEY_TRANSLATION[key]]
                        continue
                    elif key == 'transformer_repo':
                        # Special handling
                        if len(value) == 0 and isinstance(value, str):
                            assert ('transformer_repo' not in test) or \
                                   (not test['transformer_repo']) or \
                                   ('repUrl' not in test['transformer_repo'])
                        else:
                            assert (value == test['transformer_repo']['repUrl'])


def test_command_line():
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
    with open(os.path.join(working_space, result_name)) as in_file:
        res = json.load(in_file)
        assert 'code' in res
        assert res['code'] == 0

    img = gdal.Open(os.path.join(working_space, orthomosaic_mask_name)).ReadAsArray()
    assert img is not None
    assert isinstance(img, np.ndarray)
