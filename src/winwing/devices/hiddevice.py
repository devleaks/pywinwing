import os
import logging
import threading
import time
from abc import ABC, abstractmethod

import hid


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class HIDDevice(ABC):
    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id

        self.reader = threading.Event()
        self.reader.set()
        self.reader_thread: threading.Thread
        self.callback = None
        self._last_read = bytes(0)

        try:
            self.device = hid.Device(vid=self.vendor_id, pid=self.product_id)
        except hid.HIDException:
            logger.warning("could not open device", exc_info=True)
            os._exit(-1)
        logger.info("device connected")
        self.busy_writing = threading.Lock()
        self.init()

    def init(self):
        pass

    def read(self, size: int, milliseconds: int) -> bytes:
        return self.device.read(size, milliseconds)

    def write(self, message):
        self.device.write(message)

    def set_callback(self, callback):
        self.callback = callback

    def start(self):
        if self.reader.is_set():
            self.reader.clear()
            self.reader_thread = threading.Thread(target=self._reader_loop, name="MCDU Keystroke Reader")
            self.reader_thread.start()

    def stop(self):
        if not self.reader.is_set():
            self.reader.set()

    @abstractmethod
    def _reader_loop(self):
        while not self.reader.is_set():
            try:
                data_in = self.device.read(size=25, timeout=100)
            except:
                logger.warning("read error", exc_info=True)
                time.sleep(0.5)  # @todo: remove?
                continue
            if self.callback is not None:
                self._last_read = data_in
                self.callback(data_in)

    def terminate(self):
        self.stop()
        self.device.close()
