"""Contains transformer configuration information
"""
from agpypeline.configuration import Configuration


class ConfigurationSoilmask(Configuration):
    """Configuration information for Soil Mask transformer"""
    # Silence this error until we have public methods
    # pylint: disable=too-few-public-methods

    # The version number of the transformer
    transformer_version = '2.0'

    # The transformer description
    transformer_description = 'Stereo RGB Image Enhancement & Masking'

    # Short name of the transformer
    transformer_name = 'terra.stereo-rgb.rgbmask'

    # The name of the author of the extractor
    author_name = 'Chris Schnaufer'

    # The email of the author of the extractor
    author_email = 'schnaufer@email.arizona.edu'

    # Repository URI of where the source code lives
    repository = 'https://github.com/Chris-Schnaufer/rgbmask.git'

    # Contributors to this transformer
    contributors = ['Max Burnette', 'Zongyang Li', 'Todd Nicholson']

    # The sensor associated with the transformer
    transformer_sensor = 'stereoTop'

    # The transformer type (eg: 'rgbmask', 'plotclipper')
    transformer_type = 'rgb_mask'
