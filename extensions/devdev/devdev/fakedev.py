import logging
from typing import List

from xpwebapi import CALLBACK_TYPE

from winwing.devices import WinwingDevice, HIDDevice

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class FakeDev(HIDDevice):

    def __init__(self, vendor_id: int, product_id: int, **kwargs):
        HIDDevice.__init__(self, vendor_id=vendor_id, product_id=product_id)

    def _reader_loop(self):
        while not self.reader.is_set():
            try:
                data_in = self.device.read(size=25, timeout=100)
            except:
                logger.warning("read error", exc_info=True)
                continue
            if self.callback is not None:
                self._last_read = data_in
                self.callback(data_in)
            print("received", data_in)

class FakeWinwing(WinwingDevice):
    """Note: To handle non winwing devices, we need to add their VENDOR_ID to

       WinwingDevice.VENDOR_IDS

       (there is no mechanism to dynamically add vendor ids)

    """

    WINWING_PRODUCT_IDS = [1]
    VERSION = "0.0.1"

    def __init__(self, vendor_id: int, product_id: int, **kwargs):
        WinwingDevice.__init__(self, vendor_id=vendor_id, product_id=product_id)
        self._ready = False
        self.device = FakeDev(vendor_id=vendor_id, product_id=product_id)

        # self.api = ws_api(host=kwargs.get("host", "127.0.0.1"), port=kwargs.get("port", "8086"))
        self.api = None  # ws_api(host="192.168.1.140", port="8080")

    def set_api(self, api):
        self.api = api
        self.api.add_callback(CALLBACK_TYPE.ON_DATAREF_UPDATE, self.on_dataref_update)

    def set_extension_paths(self, extension_paths: List[str]):
        pass

    def on_dataref_update(self, dataref: str, value):
        print(dataref, value)

    def run(self):
        """Starts device handling"""
        pass

    def terminate(self):
        """Stop device handling"""
        pass