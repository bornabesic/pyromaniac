
import logging

# Logger
LOGGER = logging.getLogger("pyromaniac")
LOGGER.setLevel(logging.INFO)

# Console handler
_HANDLER = logging.StreamHandler()
_HANDLER.setLevel(logging.DEBUG)

# Formatter
_FORMATTER = logging.Formatter('%(name)s : %(levelname)s : %(message)s')
_HANDLER.setFormatter(_FORMATTER)
LOGGER.addHandler(_HANDLER)
