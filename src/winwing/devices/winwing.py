"""Abstract base class for all Winwing Devices like MCDU, EFIS, FCU, etc.
"""

import logging
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class WinwingDevice(ABC):

    WINWING_VENDOR_IDS = [16536]
    WINWING_PRODUCT_IDS = []
    VERSION = "0.0.1"

    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id

        # TO avoir idolating device driver specifics in a supplemental class
        # this class can be used to declare the device:
        #
        # try:
        #     self.device = hid.Device(vid=self.vendor_id, pid=self.product_id)
        # except hid.HIDException:
        #     logger.warning("could not open device", exc_info=True)
        #     self.device = None
        # logger.info("device connected")
        #

    @abstractmethod
    def run(self):
        """Starts device handling"""

    @abstractmethod
    def terminate(self):
        """Stop device handling"""

    @abstractmethod
    def set_api(self, api):
        """Stop device handling"""

    @abstractmethod
    def on_dataref_update(self, dataref: str, value):
        """Stop device handling"""
