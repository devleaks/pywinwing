"""
"""

import logging
import re
from typing import Set

from winwing.devices import mcdu
from winwing.helpers.aircraft import Aircraft
from .constant import (
    PAGE_LINES,
    PAGE_BYTES_PER_CHAR,
    PAGE_BYTES_PER_LINE,
)

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


MCDU_DISPLAY_DATA = "sim/cockpit2/radios/indicators/fms_cdu(?P<unit>[1-2]+)_(?P<name>(text|style)+)_line(?P<line>[0-9]+)"


class LaminarAircraft(Aircraft):

    AIRCRAFT_KEYS = [
        Aircraft.key(icao="A333", author="Alex Unruh, Rodrigo Fernandez, Massimo Durando, Jim Gregory, Marco Auer"),
    ]

    def __init__(self, author: str, icao: str, variant: str | None = None) -> None:
        Aircraft.__init__(self, author=author, icao=icao, variant=variant)
        self._datarefs = {}

    @property
    def mcdu_units(self) -> Set[int]:
        if not self.loaded:
            return set()
        return set(self._config.get("mcdu-units", []))

    @staticmethod
    def is_display_dataref(dataref: str) -> bool:
        return re.match(MCDU_DISPLAY_DATA, dataref) is not None

    def get_mcdu_unit(self, dataref) -> int:
        mcdu_unit = -1
        try:
            m = re.match(MCDU_DISPLAY_DATA, dataref)
            if m is None:
                logger.warning(f"not a display dataref {dataref}")
                return -1
            mcdu_unit = int(m["unit"])
        except:
            logger.warning(f"error invalid MCDU unit for {dataref}")
            return -1
        return mcdu_unit

    def variable_changed(self, dataref: str, value):
        self._datarefs[dataref] = value

    def show_page(self, mcdu_unit: int) -> list:
        page = [[" " for _ in range(PAGE_BYTES_PER_LINE)] for _ in range(PAGE_LINES)]

        # See https://developer.x-plane.com/article/datarefs-for-the-cdu-screen/
        font_small = False

        def get_color(s):
            XP_COLORS = ["K","C","R","Y","G","M","A","W"]  # 0..7, see https://developer.x-plane.com/article/datarefs-for-the-cdu-screen/
            large = s & (1 << 6)
            reverse = s & (1 << 5)
            flashing = s & (1 << 4)
            underscore = s & (1 << 3)
            xp_color = s & 0x07
            print(f"{s:08b}", f"L={large} {reverse} {flashing} {underscore} C={xp_color:03b}", XP_COLORS[xp_color])
            return large == 0, XP_COLORS[xp_color]

        def show_line(lnum, fs):
            line = self._datarefs.get(f"sim/cockpit2/radios/indicators/fms_cdu{mcdu_unit}_text_line{lnum}")
            style = bytearray(self._datarefs.get(f"sim/cockpit2/radios/indicators/fms_cdu{mcdu_unit}_style_line{lnum}"), 'ascii')
            if len(style) < 24:
                style = style + b'\0' * (24 - len(style))
            print("style", lnum, line, style, len(style))
            pos = 0
            for c in line:
                if c == "←":
                    c = chr(60)
                t = get_color(style[pos])
                page[lnum][pos * PAGE_BYTES_PER_CHAR] = t[1]  # color
                page[lnum][pos * PAGE_BYTES_PER_CHAR + 1] = t[0]
                page[lnum][pos * PAGE_BYTES_PER_CHAR + 2] = c  # char
                pos = pos + 1

        for l in range(14):
            show_line(l, fs=font_small)
            font_small = not font_small

        return page
