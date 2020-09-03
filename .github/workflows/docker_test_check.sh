#!/usr/bin/env bash

# Checks the result of the  soil masking
EXPECTED_FILES=("orthomosaic_mask.tif")

# What folder are we looking in for outputs
if [[ ! "${1}" == "" ]]; then
  TARGET_FOLDER="${1}"
else
  TARGET_FOLDER="./outputs"
fi

# Check if expected files are found
for i in $(seq 0 $(( ${#EXPECTED_FILES[@]} - 1 )))
do
  if [[ ! -f "${TARGET_FOLDER}/${EXPECTED_FILES[$i]}" ]]; then
    echo "Expected file ${EXPECTED_FILES[$i]} is missing"
    exit 10
  fi
done
