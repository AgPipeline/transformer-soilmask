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
            for fname in resource['local_paths']:
                current_ratio, current_binMask, current_rgbMask = gen_cc_enhanced(fname)
                # TODO how to save or use these?
                # TODO this would be if we do this on a dataset, rather than individual files



if __name__ == "__main__":
    extractor = ganEnhancementExtractor()
    extractor.start()