CWD = $(shell pwd)

test:
	pytest -xv test.py

run:
	docker run --rm --mount "src=$(CWD)/test,target=/mnt,type=bind" agpipeline/soilmask:2.0 --working_space "/mnt" --metadata "/mnt/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_metadata_cleaned.json" "/mnt/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_right.tif"

local:
	./extractor/entrypoint.py --metadata ./input/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_metadata_cleaned.json --working_space ./input/ ./input/08f445ef-b8f9-421a-acf1-8b8c206c1bb8_right.tif
