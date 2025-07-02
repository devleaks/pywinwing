from __future__ import annotations
import logging

from xpwebapi import CALLBACK_TYPE, Dataref, Command

from ..winwing import WinwingDevice
from .aircraft import DAAircraft
from .device import DADriver

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class DeviceAdapterTemplate(WinwingDevice):
    """Winwing Device Adapter Template

    Coordinator between X-Plane, accessed through the Web API, and Winwing Device, accessed through its HID device driver.
    """

    WINWING_PRODUCT_IDS = [-1]

    VERSION = "0.0.1"

    def __init__(self, vendor_id: int, product_id: int, **kwargs):
        WinwingDevice.__init__(self, vendor_id=vendor_id, product_id=product_id)

        self.aircraft = DAAircraft(vendor=kwargs.get("acf_publisher"), icao=kwargs.get("acf_icao"))
        self.device = DADriver(vendor_id=vendor_id, product_id=product_id)

        self.api = kwargs.get("api")

    def run(self):
        """Starts device handling"""
        logger.debug(f"{type(self).__name__} started")

    def terminate(self):
        """Stop device handling"""
        logger.debug(f"{type(self).__name__} stopped")

    def set_api(self, api):
        """Set Web API access point to datarefs and commands"""
        self.api = api
        self.api.add_callback(CALLBACK_TYPE.ON_DATAREF_UPDATE, self.on_dataref_update)

    def on_dataref_update(self, dataref: str, value):
        """Called each time a new value for a registerd dataref arrived"""
        logger.debug(f"{dataref}={value}")
