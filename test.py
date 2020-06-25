"""
Purpose: Test soilmask
Author:  Ken Youens-Clark <kyclark@arizona.edu>
"""


import os
import json
from subprocess import getstatusoutput


# --------------------------------------------------
def test_run():
    """Test run"""

    prg = './extractor/entrypoint.py'
    assert os.path.isfile(prg)

    meta = './input/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_metadata_cleaned.json'
    image = './input/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_right.tif'
    ws = './input'
    mask = './input/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_right_mask.tif'

    if os.path.isfile(mask):
        os.remove(mask)

    cmd = f'{prg} --metadata {meta}  --working_space {ws} {image}'
    print(cmd)

    rv, out = getstatusoutput(cmd)
    assert rv == 0
    assert os.path.isfile(mask)
    assert os.path.getsize(mask) > 0 # Can I use 4941369 for size?

    maybe_json = find_json(out)
    if maybe_json:
        data = json.loads(maybe_json)
        if data:
            assert data.get('code') == 0


# --------------------------------------------------
def find_json(text):
    """
    Find the JSON by looking for '{' and '}' on single lines.
    This is a terrible assumption but it might work for now.
    """

    ret = []
    start, stop = False, False
    for line in text.splitlines():
        if line == '{':
            start = True
        elif line == '}':
            stop = True

        if start:
            ret.append(line)

        if stop:
            break

    return ''.join(ret)
