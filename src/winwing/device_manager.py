#         Python Stream Deck Library
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#
import logging
from typing import List

import hid

import winwing.devices as WW

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class DeviceManager:
    """
    Central device manager, to enumerate any attached Winwing devices. An
    instance of this class must be created in order to detect and use any
    StreamDeck devices.
    """

    @staticmethod
    def new(vendor_id: int, product_id: int) -> WW.WinwingDevice | None:

        adapters = DeviceManager.adapters()
        logger.debug(f"adapters {adapters}")
        reqadptr = list(filter(lambda x: vendor_id in x.WINWING_VENDOR_IDS and product_id in x.WINWING_PRODUCT_IDS, adapters))
        logger.debug(f"adapter for {vendor_id},{product_id}: {reqadptr}")
        if len(reqadptr) == 0:
            logger.warning(f"no device handler for HID device {vendor_id}, {product_id}")
            return None
        if len(reqadptr) > 1:
            logger.warning(f"More than one handler for HID device {vendor_id}, {product_id}: {reqadptr}")
            return None
        adapter = reqadptr[0]
        logger.info(f"adapter for {vendor_id},{product_id} is {adapter}")
        return adapter(vendor_id=vendor_id, product_id=product_id)

    @staticmethod
    def enumerate() -> List[WW.WinwingDevice]:
        """
        Detect attached StreamDeck devices.

        :rtype: list(StreamDeck)
        :return: list of :class:`StreamDeck` instances, one for each detected device.
        """
        devices = []
        for dev in hid.enumerate():
            if dev["vendor_id"] in WW.WinwingDevice.WINWING_VENDOR_IDS:
                devices.append(DeviceManager.new(dev["vendor_id"], dev["product_id"]))
        return devices

    @staticmethod
    def adapters() -> list:
        """Returns the list of all subclasses.

        Recurses through all sub-sub classes

        Returns:
            [list]: list of all subclasses

        Raises:
            ValueError: If invalid class found in recursion (types, etc.)
        """
        subclasses = set()
        stack = []
        try:
            stack.extend(WW.WinwingDevice.__subclasses__())
        except (TypeError, AttributeError) as ex:
            raise ValueError("Invalid class" + repr(WW.WinwingDevice)) from ex
        while stack:
            sub = stack.pop()
            subclasses.add(sub)
            try:
                stack.extend(s for s in sub.__subclasses__() if s not in subclasses)
            except (TypeError, AttributeError):
                continue
        return list(subclasses)

