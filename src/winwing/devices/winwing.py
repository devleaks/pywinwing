from abc import ABC, abstractmethod


class WinwingDevice(ABC):

    WINWING_VENDOR_IDS = [16536]

    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id

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
