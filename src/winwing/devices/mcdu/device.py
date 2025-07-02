import os
import logging
import threading
import time
from typing import Tuple

import hid
from winwing.devices import mcdu

from .constant import (
    MCDU_ANNUNCIATORS,
    MCDU_BRIGHTNESS,
    MCDU_DEVICE_MASKS,
    MCDU_INIT_SEQUENCE,
    COLOR_MAP,
    PAGE_LINES,
    PAGE_CHARS_PER_LINE,
    PAGE_BYTES_PER_CHAR,
)

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

WINWING_MCDU_DEVICES = [
    {"vid": 0x4098, "pid": 0xBB36, "name": "MCDU - Captain", "mask": MCDU_DEVICE_MASKS.MCDU | MCDU_DEVICE_MASKS.CAP},
    {"vid": 0x4098, "pid": 0xBB3E, "name": "MCDU - First Offizer", "mask": MCDU_DEVICE_MASKS.MCDU | MCDU_DEVICE_MASKS.FO},
    {"vid": 0x4098, "pid": 0xBB3A, "name": "MCDU - Observer", "mask": MCDU_DEVICE_MASKS.MCDU | MCDU_DEVICE_MASKS.OBS},
]


class MCDUDevice:
    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id

        self.reader = threading.Event()
        self.reader.set()
        self.reader_thread: threading.Thread
        self.callback = None
        self._last_read = bytes(0)

        self.mcdu_unit = self.get_mcdu_mask()
        try:
            self.device = hid.Device(vid=self.vendor_id, pid=self.product_id)
        except hid.HIDException:
            logger.warning("could not open device", exc_info=True)
            os._exit(-1)
        logger.info("device connected")
        self.busy_writing = threading.Lock()
        self.init()

    def get_mcdu_mask(self) -> int:
        """Returns first device that matches Winwing' signature"""
        mcdu_unit = MCDU_DEVICE_MASKS.NONE
        for d in WINWING_MCDU_DEVICES:
            if self.vendor_id == d["vid"] and self.product_id == d["pid"]:
                mcdu_unit |= d["mask"]
                logger.debug(f"MCDU unit {mcdu_unit}")
                return mcdu_unit
        logger.warning("MCDU unit not found")
        return mcdu_unit

    def init(self):
        for s in MCDU_INIT_SEQUENCE(background_color=[0x00, 0x00, 0x00]):
            self.device.write(bytes(s))

    @property
    def mcdu_unit_id(self) -> int:
        if self.mcdu_unit & MCDU_DEVICE_MASKS.FO:
            return 2
        elif self.mcdu_unit & MCDU_DEVICE_MASKS.OBS:
            return 3
        if not (self.mcdu_unit & MCDU_DEVICE_MASKS.CAP):
            logger.warning(f"no unit {self.mcdu_unit}, returning default 1")
        return 1

    def set_unit(self, unit: MCDU_DEVICE_MASKS):
        self.mcdu_unit = MCDU_DEVICE_MASKS.MCDU | unit

    def set_unit_led(self, on: bool = True):
        # self.set_led(led=MCDU_ANNUNCIATORS.FM1, on=False)
        # self.set_led(led=MCDU_ANNUNCIATORS.FM2, on=False)
        if self.mcdu_unit & MCDU_DEVICE_MASKS.FO:
            self.set_led(led=MCDU_ANNUNCIATORS.FM2, on=on)
            return
        self.set_led(led=MCDU_ANNUNCIATORS.FM1, on=on)

    def read(self, size: int, milliseconds: int) -> bytes:
        return self.device.read(size, milliseconds)

    def write(self, message):
        self.device.write(message)

    def set_brightness(self, backlight: MCDU_BRIGHTNESS, brightness: int):
        b = max(0, min(int(brightness), 255))
        set_brightness_msg = [0x02, 0x32, 0xBB, 0, 0, 3, 0x49, backlight.value, b, 0, 0, 0, 0, 0]
        self.device.write(bytes(set_brightness_msg))

    def set_led(self, led: MCDU_ANNUNCIATORS, on: bool):
        set_led_msg = [0x02, 0x32, 0xBB, 0, 0, 3, 0x49, led.value, 1 if on else 0, 0, 0, 0, 0, 0]
        self.device.write(bytes(set_led_msg))

    def _character_code(self, color: int | str, font_small: bool = False) -> Tuple[int, int]:
        if type(color) is int:
            color = chr(color)
        color = color.upper()
        if color not in COLOR_MAP:
            logger.warning(f"invalid color {color}, using white")
            color = "W"
        color = COLOR_MAP[color] + 0x016B if font_small else COLOR_MAP[color]
        return (color & 0x0FF, (color >> 8) & 0xFF)

    def clear(self):
        blank_line = [0xF2] + [0x42, 0x00, ord(" ")] * PAGE_CHARS_PER_LINE
        for _ in range(16):
            self.device.write(bytes(blank_line))

    def display_page(self, page: list, vertslew_key: int = 0):
        """[summary]

        A Page is a list of Line.
        Each Line is a list of sets of 3 bytes:
            1. color/font low byte
            2. color/font high byte
            3. ASCII code of char, modified for special characters
        All bytes are collected first in a big array.
        Then array is sent by sets of 63 bytes (=21 characters) + one byte to set the type of message sent (.insert(0, 0xF2))

        Args:
            page (list): [description]
            vertslew_key (int): [description] (default: `0`)
        """
        # Encore a page into a single buffer of 3 byte set.
        buf = []
        for i in range(PAGE_LINES):
            for j in range(PAGE_CHARS_PER_LINE):
                color = page[i][j * PAGE_BYTES_PER_CHAR]
                font_small = page[i][j * PAGE_BYTES_PER_CHAR + 1]
                data_low, data_high = self._character_code(color, font_small)
                buf.append(data_low)
                buf.append(data_high)
                val = ord(page[i][j * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1])
                if val > 255:
                    print("error", page[i][j * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1], val, i, j)
                if val == 35:  # #
                    buf.extend([0xE2, 0x98, 0x90])
                elif val == 60:  # <
                    buf.extend([0xE2, 0x86, 0x90])
                elif val == 62:  # >
                    buf.extend([0xE2, 0x86, 0x92])
                elif val == 96:  # °
                    buf.extend([0xC2, 0xB0])
                # elif val == "A": # down arrow
                #    buf.extend([0xe2, 0x86, 0x93])
                # elif val == "ö": # up arrow
                #    buf.extend([0xe2, 0x86, 0x91])
                else:
                    if i == PAGE_LINES - 1 and j == PAGE_CHARS_PER_LINE - 2 and (vertslew_key == 1 or vertslew_key == 2):
                        buf.extend([0xE2, 0x86, 0x91])
                    elif i == PAGE_LINES - 1 and j == PAGE_CHARS_PER_LINE - 1 and (vertslew_key == 1 or vertslew_key == 3):
                        buf.extend([0xE2, 0x86, 0x93])
                    else:
                        buf.append(val)

        self.write_buffer(buffer=buf)

    def write_buffer(self, buffer: bytes):
        buf = buffer
        with self.busy_writing:
            while len(buf) > 0:
                max_len = min(63, len(buf))
                msg_buf = buf[:max_len]
                msg_buf.insert(0, 0xF2)
                if max_len < 63:
                    msg_buf.extend([0] * (63 - max_len))
                self.device.write(bytes(msg_buf))
                del buf[:max_len]

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

    def _reader_loop(self):
        while not self.reader.is_set():
            try:
                data_in = self.device.read(size=25, timeout=100)
            except:
                logger.warning("read error", exc_info=True)
                time.sleep(0.5)  # @todo: remove?
                continue
            if len(data_in) == 14:  # we get this often but don"t understand yet. May have someting to do with leds set
                continue
            if len(data_in) != 25:
                print(f"invalid rx data count {len(data_in)}/25")
                continue
            if self.callback is not None:
                self._last_read = data_in
                self.callback(data_in)

    def light_sensors(self):
        if len(self._last_read) > 20:
            return self._last_read[17], self._last_read[19]
        return 0, 0

    def terminate(self):
        self.stop()
        self.device.close()