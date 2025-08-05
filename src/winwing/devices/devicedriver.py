import logging
import threading

from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class DeviceDriver(ABC):
    def __init__(self):

        self.reader = threading.Event()
        self.reader.set()
        self.reader_thread: threading.Thread
        self.callback = None
        self._last_read = bytes(0)
        self.busy_writing = threading.Lock()
        self.init()

    def init(self):
        pass

    def set_callback(self, callback):
        self.callback = callback

    @abstractmethod
    def read(self, size: int, timeout: int) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write(self, message):
        raise NotImplementedError

    def _reader_loop(self):
        while not self.reader.is_set():
            try:
                data_in = self.read(size=25, timeout=100)
                if self.callback is not None:
                    self._last_read = data_in
                    self.callback(data_in)
            except:
                logger.warning("read error", exc_info=True)
                continue

    def start(self):
        if self.reader.is_set():
            self.reader.clear()
            self.reader_thread = threading.Thread(target=self._reader_loop, name="MCDU Keystroke Reader")
            self.reader_thread.start()

    def stop(self):
        if not self.reader.is_set():
            self.reader.set()

    def terminate(self):
        self.stop()
        self.device.close()
