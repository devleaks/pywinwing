"""Abstract base class for Winwing device drivers that use the HID protocol.

Device drivers are the module that communicate directly with the device,
either to read data from it, or send data to it.

In the case of HID device/protocol, communication is done through "reports",
although they are seldom built from streams of bytes rather than "logical" entities.
"""
import os
import logging

import hid

from .devicedriver import DeviceDriver

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class HIDDevice(DeviceDriver):
    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id

        self._last_read = bytes(0)

        try:
            self.device = hid.Device(vid=self.vendor_id, pid=self.product_id)
        except hid.HIDException:
            logger.warning("could not open device", exc_info=True)
            os._exit(-1)
        logger.info("device connected")

        DeviceDriver.__init__(self)  # calls init()

    def read(self, size: int, timeout: int) -> bytes:
        return self.device.read(size, timeout)

    def write(self, message):
        self.device.write(message)
