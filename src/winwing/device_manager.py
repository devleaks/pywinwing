"""Device Manager

Helper class to collect and display device information

"""
import logging
from typing import List

import hid

# Important: The following loads all known devices from devices.__init__.py.
# All devices should be loaded in that module.
import winwing.devices as WW

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class DeviceManager:
    """
    Central device manager, to enumerate any attached Winwing devices,
    and device adapters available.
    """

    @staticmethod
    def new(vendor_id: int, product_id: int) -> WW.WinwingDevice | None:
        """Create device adapter for supplied (vendor, product)

        If no device adapter can be found, returns None

        Args:
            vendor_id (int): HID vendor identifier (2 bytes)
            product_id (int): HID product identifier (2 bytes) for above vendor

        Returns:
            [WinwingDevice]: Device adapter
        """

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
        Detect attached Winwing devices.

        :rtype: list(WinwingDevice)
        :return: list of :class:`WinwingDevice` instances, one for each detected device.
        """
        devices = []
        for dev in hid.enumerate():
            if dev["vendor_id"] in WW.WinwingDevice.WINWING_VENDOR_IDS:
                device = DeviceManager.new(dev["vendor_id"], dev["product_id"])
                if device is not None:
                    devices.append(device)
        return devices

    @staticmethod
    def adapters() -> list:
        """Returns the list of all subclasses of WinwingDevice.

        Recurses through all sub-sub classes

        Returns:
            [list]: list of all WinwingDevice subclasses

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
