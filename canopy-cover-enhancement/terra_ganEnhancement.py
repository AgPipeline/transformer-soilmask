import os
import shutil
import tempfile
from ganEnhancement import gen_cc_enhanced

from pyclowder.utils import CheckMessage
from terrautils.extractors import TerrarefExtractor

class ganEnhancementExtractor(TerrarefExtractor):
    def __init__(self):
        super(ganEnhancementExtractor, self).__init__()

        # parse command line and load default logging configuration
        self.setup(sensor='ganEnhancement')

        def check_message(self, connector, host, secret_key, resource, parameters):
            # TODO not sure what rules should be checked here, returning true
            return CheckMessage.download

        def process_message(self, connector, host, secret_key, resource, parameters):
            self.start_message(resource)

if __name__ == "__main__":
    extractor = ganEnhancementExtractor()
    extractor.start()