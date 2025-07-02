import logging

import hid

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class DADriver:
    """Winwing Device Adapter Drive

    Handles interaction with device through HID.
    """

    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id

        try:
            self.device = hid.Device(vid=self.vendor_id, pid=self.product_id)
        except hid.HIDException:
            logger.warning("could not open device", exc_info=True)
            self.device = None
        logger.info("device connected")
