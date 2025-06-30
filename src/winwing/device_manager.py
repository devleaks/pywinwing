#         Python Stream Deck Library
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#
import hid

from typing import List

from .devices.winwing import WinwingDevice

from .devices.mcdu import MCDU

WINWING_VENDOR_IDS = [16536]


class DeviceManager:
    """
    Central device manager, to enumerate any attached Winwing devices. An
    instance of this class must be created in order to detect and use any
    StreamDeck devices.
    """

    @staticmethod
    def new(vendor_id: int, product_id: int) -> WinwingDevice:
        if product_id in [47926]:
            return MCDU(vendor_id=vendor_id, product_id=product_id)

    @staticmethod
    def enumerate() -> List[WinwingDevice]:
        """
        Detect attached StreamDeck devices.

        :rtype: list(StreamDeck)
        :return: list of :class:`StreamDeck` instances, one for each detected device.
        """
        devices = []
        for dev in hid.enumerate():
            if dev["vendor_id"] in WINWING_VENDOR_IDS:
                devices.append(DeviceManager.new(dev["vendor_id"], dev["product_id"]))
        return devices
