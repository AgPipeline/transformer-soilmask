"""Class instance for Transformer
"""

import argparse

# pylint: disable=unused-argument
class Transformer():
    """Generic class for supporting transformers
    """
    def __init__(self, **kwargs):
        """Performs initialization of class instance
        Arguments:
            kwargs: additional parameters passed into Transformer instance
        """
        self.args = None

    def add_parameters(self, parser: argparse.ArgumentParser) -> None:
        """Adds processing parameters to existing parameters
        Arguments:
            parser: instance of argparse
        """

    # pylint: disable=no-self-use
    def get_transformer_params(self, args: argparse.Namespace, metadata: list) -> dict:
        """Returns a parameter list for processing data
        Arguments:
            args: result of calling argparse.parse_args
            metadata: the list of loaded metadata
        Return:
            A dictionary of parameter names and value to pass to transformer
        """
        self.args = args

        params = {}
        return params

    # pylint: disable=no-self-use
    def retrieve_files(self, transformer_params: dict, metadata: list) -> tuple:
        """Retrieves files as needed to make them available for processing
        Arguments:
            transformer_params: the values returned from get_transformer_params() call
            metadata: the loaded metadata
        Return:
            A tuple consisting of the return code and an optional error message.
        Notes:
            A negative return code is considered an error and an associated message, if specified,
            will be  treated as such.
        """
        return 0, "everything's in order"
