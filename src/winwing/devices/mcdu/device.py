import os
import logging
import threading
import time
from enum import IntEnum
from typing import Tuple

import hid

from .constant import (
    MCDU_ANNUNCIATORS,
    MCDU_BRIGHTNESS,
    MCDU_DEVICE_MASKS,
    MCDU_INIT_SEQUENCE,
    COLORS,
    PAGE_LINES,
    PAGE_CHARS_PER_LINE,
    PAGE_BYTES_PER_CHAR,
)

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

WINWING_MCDU_DEVICES = [
    {"vid": 0x4098, "pid": 0xBB36, "name": "MCDU - Captain", "mask": MCDU_DEVICE_MASKS.MCDU | MCDU_DEVICE_MASKS.CAP},
    {"vid": 0x4098, "pid": 0xBB3E, "name": "MCDU - First Officer", "mask": MCDU_DEVICE_MASKS.MCDU | MCDU_DEVICE_MASKS.FO},
    {"vid": 0x4098, "pid": 0xBB3A, "name": "MCDU - Observer", "mask": MCDU_DEVICE_MASKS.MCDU | MCDU_DEVICE_MASKS.OBS},
]


class SPECIAL_CHARACTERS(IntEnum):
    ARROW_LEFT = 9900
    ARROW_UP = 9901
    ARROW_RIGHT = 9902
    ARROW_DOWN = 9903
    DEGREE = 9904
    SQUARE_BRACKET_OPEN = 9905
    SQUARE_BRACKET_CLOSE = 9906
    SQUARE = 9907
    HEXAGON = 9908
    TRIANGLE_LEFT = 9910
    TRIANGLE_RIGHT = 9911
    DELTA = 9912
    TEST = 9913

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
        for s in MCDU_INIT_SEQUENCE:
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

    def _character_code(self, color: COLORS, font_small: bool = False) -> Tuple[int, int]:
        color_mask = color.ww_mask + 0x016B if font_small else color.ww_mask
        return (color_mask & 0x0FF, (color_mask >> 8) & 0xFF)

    def clear(self):
        blank_line = [0xF2] + [0x42, 0x00, ord(" ")] * PAGE_CHARS_PER_LINE
        for _ in range(16):
            self.device.write(bytes(blank_line))

    def display_page(self, page: list):
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
        """
        # Encore a page into a single buffer of 3 byte set.
        buf = []
        for i in range(PAGE_LINES):
            for j in range(PAGE_CHARS_PER_LINE):
                # Style
                color = page[i][j * PAGE_BYTES_PER_CHAR]
                font_small = page[i][j * PAGE_BYTES_PER_CHAR + 1]
                data_low, data_high = self._character_code(color, font_small)
                if data_low > 255:
                    logger.error(f"data_low: {page[i][j * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1]}, {color}, {font_small}, {i}, {j}")
                if data_high > 255:
                    logger.error(f"data_high: {page[i][j * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1]}, {color}, {font_small}, {i}, {j}")
                buf.append(data_low)
                buf.append(data_high)
                # Character
                val = ord(page[i][j * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1])

                # Replace special chars with UTF-8 bytes
                #   (UTF-16, UTF-8)
                # ° (00B0, 0xC2 0xB0)
                # ← (2190, 0xE2 0x86 0x90)
                # ↑ (2191, 0xE2 0x86 0x91)
                # → (2192, 0xE2 0x86 0x92)
                # ↓ (2193, 0xE2 0x86 0x93)
                # ☐ (2610, 0xE2 0x98 0x90
                # Δ (0394, 0xCE 0x94)
                # ⬡ (2B21, 0xE2 0xAC 0xA1)
                # ◀ (25C0, 0xE2 0x97 0x80)
                # ▶ (25B6, 0xE2 0x96 0xB6)
                if val == SPECIAL_CHARACTERS.DEGREE.value:  # °
                    buf.extend([0xC2, 0xB0])
                elif val == SPECIAL_CHARACTERS.SQUARE.value:  # ☐
                    buf.extend([0xE2, 0x98, 0x90])
                elif val == SPECIAL_CHARACTERS.ARROW_LEFT.value:  # ←
                    buf.extend([0xE2, 0x86, 0x90])
                elif val == SPECIAL_CHARACTERS.ARROW_UP.value:  # ↑
                    buf.extend([0xE2, 0x86, 0x91])
                elif val == SPECIAL_CHARACTERS.ARROW_RIGHT.value:  # →
                    buf.extend([0xE2, 0x86, 0x92])
                elif val == SPECIAL_CHARACTERS.ARROW_DOWN.value:  # ↓
                    buf.extend([0xE2, 0x86, 0x93])
                elif val == SPECIAL_CHARACTERS.HEXAGON.value:  # ⬡
                    buf.extend([0xE2, 0xAC, 0xA1])
                elif val == SPECIAL_CHARACTERS.TRIANGLE_LEFT.value:  # ◀
                    buf.extend([0xE2, 0x97, 0x80])
                elif val == SPECIAL_CHARACTERS.TRIANGLE_RIGHT.value:  # ▶
                    buf.extend([0xE2, 0x96, 0xB6])
                elif val == SPECIAL_CHARACTERS.SQUARE_BRACKET_OPEN.value:  # ⬡
                    buf.append(ord("["))
                elif val == SPECIAL_CHARACTERS.SQUARE_BRACKET_CLOSE.value:  # ⬡
                    buf.append(ord("]"))
                elif val == SPECIAL_CHARACTERS.DELTA.value:  # ⬡
                    buf.extend([0xCE, 0x94])
                elif val == SPECIAL_CHARACTERS.TEST.value:  # ⬡
                    buf.extend([0xE2, 0x98, 0x89])  # sun = [0xE2, 0x98, 0x89]
                else:
                    if val > 255:
                        logger.error(f"character: {page[i][j * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1]}, {val}, {i}, {j}")
                    buf.append(val)

        self.write_buffer(buffer=buf)

    def write_buffer(self, buffer: bytes):
        # check buffer first
        pos = 0
        for c in buffer:
            if c > 255:
                break
            pos = pos + 1
        if len(buffer) != pos:
            logger.warning(f"invalid buffer, no display (pos={pos}/{len(buffer)}, {buffer[pos]})")
            return

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
