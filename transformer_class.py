"""Class instance for Transformer
"""

import argparse
import datetime
import logging
from osgeo import gdal, osr
from numpy import nan
import piexif
from typing import Optional

import configuration

# EXIF tags to look for
EXIF_ORIGIN_TIMESTAMP = 36867         # Capture timestamp
EXIF_TIMESTAMP_OFFSET = 36881         # Timestamp UTC offset (general)
EXIF_ORIGIN_TIMESTAMP_OFFSET = 36881  # Capture timestamp UTC offset


class __internal__():
    """Class containing functions for this file only
    """
    def __init__(self):
        """Perform class level initialization
        """

    @staticmethod
    def image_get_geobounds(filename: str) -> list:
        """Uses gdal functionality to retrieve recilinear boundaries from the file

        Args:
            filename(str): path of the file to get the boundaries from

        Returns:
            The upper-left and calculated lower-right boundaries of the image in a list upon success.
            The values are returned in following order: min_y, max_y, min_x, max_x. A list of numpy.nan
            in each position is returned if the boundaries can't be determined
        """
        try:
            src = gdal.Open(filename)
            ulx, xres, _, uly, _, yres = src.GetGeoTransform()
            lrx = ulx + (src.RasterXSize * xres)
            lry = uly + (src.RasterYSize * yres)

            min_y = min(uly, lry)
            max_y = max(uly, lry)
            min_x = min(ulx, lrx)
            max_x = max(ulx, lrx)

            return [min_y, max_y, min_x, max_x]
        except Exception as ex:
            logging.info("[image_get_geobounds] Exception caught: %s", str(ex))
            if logging.getLogger().level == logging.DEBUG:
                logging.exception("[image_get_geobounds] Exception")

        return [nan, nan, nan, nan]

    @staticmethod
    def get_epsg(filename: str) -> Optional[str]:
        """Returns the EPSG of the georeferenced image file
        Args:
            filename(str): path of the file to retrieve the EPSG code from
        Return:
            Returns the found EPSG code, or None if it's not found or an error ocurred
        """
        logger = logging.getLogger(__name__)

        try:
            src = gdal.Open(filename)

            proj = osr.SpatialReference(wkt=src.GetProjection())

            return proj.GetAttrValue('AUTHORITY', 1)
        except Exception as ex:
            logger.warning("[get_epsg] Exception caught: %s", str(ex))
            if logging.getLogger().level == logging.DEBUG:
                logging.exception("[get_epsg] Exception")

        return None

    @staticmethod
    def exif_tags_to_timestamp(exif_tags):
        """Looks up the origin timestamp and a timestamp offset in the exit tags and returns
           a datetime object
        Args:
            exif_tags(dict): The exif tags to search for timestamp information
        Return:
            Returns the origin timestamp when found. The return timestamp is adjusted for UTF if
            an offset is found. None is returned if a valid timestamp isn't found.
        """
        cur_stamp, cur_offset = (None, None)

        def convert_and_clean_tag(value):
            """Internal helper function for handling EXIF tag values. Tests for an empty string after
               stripping colons, '+', '-', and whitespace [the spec is unclear if a +/- is needed when
               the timestamp offset is unknown (and spaces are used)].
            Args:
                value(bytes or str): The tag value
            Return:
                Returns the cleaned up, and converted from bytes, string. Or None if the value is empty
                after stripping above characters and whitespace.
            """
            if not value:
                return None

            # Convert bytes to string
            if isinstance(value, bytes):
                value = value.decode('UTF-8').strip()
            else:
                value = value.strip()

            # Check for an empty string after stripping colons
            if value:
                if not value.replace(":", "").replace("+:", "").replace("-", "").strip():
                    value = None

            return None if not value else value

        # Process the EXIF data
        if EXIF_ORIGIN_TIMESTAMP in exif_tags:
            cur_stamp = convert_and_clean_tag(exif_tags[EXIF_ORIGIN_TIMESTAMP])
        if not cur_stamp:
            return None

        if EXIF_ORIGIN_TIMESTAMP_OFFSET in exif_tags:
            cur_offset = convert_and_clean_tag(exif_tags[EXIF_ORIGIN_TIMESTAMP_OFFSET])
        if not cur_offset and EXIF_TIMESTAMP_OFFSET in exif_tags:
            cur_offset = convert_and_clean_tag(exif_tags[EXIF_TIMESTAMP_OFFSET])

        # Format the string to a timestamp and return the result
        try:
            if not cur_offset:
                cur_ts = datetime.datetime.fromisoformat(cur_stamp)
            else:
                cur_offset = cur_offset.replace(":", "")
                cur_ts = datetime.datetime.fromisoformat(cur_stamp + cur_offset)
        except Exception as ex:
            cur_ts = None
            logging.debug("Exception caught converting EXIF tag to timestamp: %s", str(ex))

        return cur_ts

    @staticmethod
    def get_first_timestamp(file_path: str, timestamp: str = None) -> str:
        """Looks for a timestamp in the specified file and returns
           the earliest timestamp (when compared to the timestamp parameter)
        Arguments:
            file_path: the path to the file to check
            timestamp: the timestamp to compare against (when specified)
        Return:
            The earliest found timestamp
        """
        first_stamp = datetime.datetime.fromisoformat(timestamp) if timestamp else None
        try:
            tags_dict = piexif.load(file_path)
            if tags_dict and "Exif" in tags_dict:
                cur_stamp = __internal__.exif_tags_to_timestamp(tags_dict["Exif"])
                if cur_stamp:
                    first_stamp = cur_stamp if first_stamp is None or cur_stamp < first_stamp else first_stamp
        except Exception as ex:
            logging.debug("Exception caught getting timestamp from file: %s", file_path)
            logging.debug("    %s", str(ex))

        if first_stamp:
            return first_stamp.isoformat()

        return timestamp


class Transformer():
    """Generic class for supporting transformers
    """

    def __init__(self, **kwargs):
        """Performs initialization of class instance
        Arguments:
            kwargs: additional parameters passed in to Transformer
        """
        # pylint: disable=unused-argument
        self.sensor = None
        self.args = None

    @property
    def default_epsg(self) -> int:
        """Returns the current working EPSG code
        """
        return 4326

    @property
    def supported_image_file_exts(self):
        """Returns the list of supported image file extension strings (in lower case)
        """
        return ['tif', 'tiff', 'jpg']

    def get_image_file_epsg(self, source_path: str) -> str:
        """Returns the EPSG of the georeferenced image file
        Arguments:
            source_path: the path to the image to load the EPSG code from
        Return:
            Returns the EPSG code loaded from the file. None is returned if there is a problem or the file
            doesn't have an EPSG code
        """
        # pylint: disable=no-self-use
        return __internal__.get_epsg(source_path)

    def get_image_file_geobounds(self, source_path: str) -> list:
        """Uses gdal functionality to retrieve rectilinear boundaries from the file
        Args:
            source_path(str): path of the file to get the boundaries from
        Returns:
            The upper-left and calculated lower-right boundaries of the image in a list upon success.
            The values are returned in following order: min_y, max_y, min_x, max_x. A list of numpy.nan
            is returned if the boundaries can't be determined
        """
        # pylint: disable=no-self-use
        return __internal__.image_get_geobounds(source_path)

    def generate_transformer_md(self) -> dict:
        """Generates metadata about this transformer
        Returns:
            Returns the transformer metadata
        """
        # pylint: disable=no-self-use
        return {
            'version': configuration.TRANSFORMER_VERSION,
            'name': configuration.TRANSFORMER_NAME,
            'author': configuration.AUTHOR_NAME,
            'description': configuration.TRANSFORMER_DESCRIPTION,
            'repository': {'repUrl': configuration.REPOSITORY}
        }

    def add_parameters(self, parser: argparse.ArgumentParser) -> None:
        """Adds processing parameters to existing parameters
        Arguments:
            parser: instance of argparse
        """
        # pylint: disable=no-self-use
        parser.epilog = configuration.TRANSFORMER_NAME + ' version ' + configuration.TRANSFORMER_VERSION + \
                        ' author ' + configuration.AUTHOR_NAME + ' ' + configuration.AUTHOR_EMAIL

    def get_transformer_params(self, args: argparse.Namespace, metadata: list) -> dict:
        """Returns a parameter list for processing data
        Arguments:
            args: result of calling argparse.parse_args
            metadata: the loaded metadata
        """
        # Disabling this warning to keep code readable
        # pylint: disable=too-many-branches
        self.args = args

        timestamp, season_name, experiment_name = None, None, None
        parsed_metadata = []
        transformer_md = []

        # Loop through the metadata
        for one_metadata in metadata:
            # Determine if we're using JSONLD
            if 'content' in one_metadata:
                parse_md = one_metadata['content']
            else:
                parse_md = one_metadata
            # Check for legacy 'pipeline' key
            if 'pipeline' in parse_md:
                parse_md = parse_md['pipeline']
            parsed_metadata.append(parse_md)

            # Get the season, experiment, etc information
            if 'observationTimeStamp' in parse_md:
                timestamp = parse_md['observationTimeStamp']
            if 'season' in parse_md:
                season_name = parse_md['season']
            if 'studyName' in parse_md:
                experiment_name = parse_md['studyName']

            # Check for transformer specific metadata
            if configuration.TRANSFORMER_NAME in parse_md:
                if isinstance(parse_md[configuration.TRANSFORMER_NAME], list):
                    transformer_md.extend(parse_md[configuration.TRANSFORMER_NAME])
                else:
                    transformer_md.append(parse_md[configuration.TRANSFORMER_NAME])
        # Get the list of files, if there are some and find the earliest timestamp if a timestamp
        # hasn't been specified yet
        file_list = []
        working_timestamp = timestamp
        if args.file_list:
            for one_file in args.file_list:
                # Filter out arguments that are obviously not files
                if not one_file.startswith('-'):
                    file_list.append(one_file)
                    # Only bother to get a timestamp if we don't have one specified
                    if timestamp is None:
                        working_timestamp = __internal__.get_first_timestamp(one_file, working_timestamp)
        if timestamp is None and working_timestamp is not None:
            timestamp = working_timestamp

        # Prepare our parameters
        check_md = {'timestamp': timestamp,
                    'season': season_name,
                    'experiment': experiment_name,
                    'container_name': None,
                    'target_container_name': None,
                    'trigger_name': None,
                    'context_md': None,
                    'working_folder': args.working_space,
                    'list_files': lambda: file_list
                   }

        return {'check_md': check_md,
                'transformer_md': transformer_md,
                'full_md': parsed_metadata
               }
