# Testing 

Some ideas for testing the soilmask code, starting with basic integration test from command line, eventually moving to unit testing of functions.

## Setup

You will need the "extractor" files locally:

```
id=$(docker create agdrone/transformer-soilmask:latest) && docker cp $id:/home/extractor/* ./ && docker rm $id
```

Download the input files from https://drive.google.com/file/d/1sYho-mIRhlvKEdRGYCh2bhp-DgGmi1KQ/view?usp=sharing.

Place into a directory called "input" which should contain:

```
input/
├── 08f445ef-b8f9-421a-acf1-8b8c206c1bb8_metadata_cleaned.json
├── 08f445ef-b8f9-421a-acf1-8b8c206c1bb8_right.tif
└── result.json
```

Install dependencies:

```
python3 -m pip install PyYAML piexif terrautils GDAL laspy \
cryptography cv2ools scikit-image
```

Note that GDAL Python module requires the installation of the GDAL software from https://gdal.org/. OSX can use `brew install gdal`.

## Running

If the setup is done, you should be able to run this command and see this output:

```
./extractor/entrypoint.py --metadata ./input/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_metadata_cleaned.json --working_space ./input/ ./input/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_right.tif
Input file size is 2715, 3098
0...10...20...30...40...50...60...70...80...90...100 - done.
{
  "code": 0,
  "file": [
    {
      "path": "./input/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_right_mask.tif",
      "key": "stereoTop",
      "metadata": {
        "data": {
          "name": "terra.stereo-rgb.rgbmask",
          "version": "2.0",
          "ratio": 0.15353480591648863
        }
      }
    }
  ]
}
```

And now there should be the listed "mask" file in the "input" directory.

## Testing

The `test.py` program will use `pytest` to run the above command and verify that the return value is 0 (no errors) and that the "mask" file is created:

```
pytest -xv test.py
============================= test session starts =============================
...
collected 1 item

test.py::test_run PASSED                                                [100%]

============================== 1 passed in 2.69s ==============================
```

## Author

Ken Youens-Clark <kyclark@arizona.edu>
