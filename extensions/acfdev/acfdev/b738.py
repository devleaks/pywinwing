"""
"""

import logging
from typing import Set
import winwing
from winwing.devices.mcdu.mcdu_aircraft import MCDUAircraft
from winwing.devices.mcdu.constant import COLORS

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


# #######################################@
# Display Constants
#
PAGE_LINES = 14  # Header + 6 * label + 6 * cont + textbox
PAGE_CHARS_PER_LINE = 24
PAGE_BYTES_PER_CHAR = 3
PAGE_BYTES_PER_LINE = PAGE_CHARS_PER_LINE * PAGE_BYTES_PER_CHAR
PAGE_BYTES_PER_PAGE = PAGE_BYTES_PER_LINE * PAGE_LINES


class B738(MCDUAircraft):

    VERSION = "7.3.8"

    AIRCRAFT_KEYS = [
        MCDUAircraft.key(icao="B738", author="Alex Unruh"),
    ]

    def __init__(self, author: str, icao: str, variant: str | None = None) -> None:
        MCDUAircraft.__init__(self, author=author, icao=icao, variant=variant)
        self._datarefs = {}

    @property
    def mcdu_units(self) -> Set[int]:
        if not self.loaded:
            return set()
        return set(self._config.get("mcdu-units", []))

    def set_mcdu_unit(self, str_in: str, mcdu_unit: int):
        return str_in

    @staticmethod
    def is_display_dataref(dataref: str) -> bool:
        return True

    def variable_changed(self, dataref: str, value):
        self._datarefs[dataref] = value

    def get_mcdu_unit(self, dataref) -> int:
        return 1

    def encode_bytes(self, dataref, value) -> str | bytes:
        try:
            return value.decode("ascii").replace("\u0000", "")
        except:
            logger.warning(f"cannot decode bytes for {dataref.name} (encoding=ascii)", exc_info=True)
        return value

    def show_page(self, mcdu_unit) -> list:
        page = []
        for i in range(PAGE_LINES):
            line = []
            for j in range(PAGE_CHARS_PER_LINE):
                line.extend([COLORS.DEFAULT, False, " "])
            page.append(line)

        def write_line_to_page(line, pos, text: str, color: COLORS, font_small: bool = False):
            pos = pos * PAGE_BYTES_PER_CHAR
            for c in range(len(text)):
                page[line][pos + c * PAGE_BYTES_PER_CHAR] = color
                page[line][pos + c * PAGE_BYTES_PER_CHAR + 1] = font_small
                page[line][pos + c * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1] = text[c]

        def center_line(line: int, text: str, color: COLORS, font_small: bool = False):
            text = text[:PAGE_CHARS_PER_LINE]
            startpos = int((PAGE_CHARS_PER_LINE - len(text)) / 2)
            write_line_to_page(line, startpos, text, color, font_small)

        # Heading
        title = "WINWING for X-Plane"
        idx = title.index("G") + int((PAGE_CHARS_PER_LINE - len(title)) / 2)
        center_line(0, title, COLORS.DEFAULT)
        page[0][idx * PAGE_BYTES_PER_CHAR] = COLORS.RED

        # Message
        center_line(6, "MCDU is for Airbus", COLORS.AMBER)
        center_line(7, "aircrafts only", COLORS.AMBER)
        h = self._datarefs.get("sim/cockpit2/clock_timer/zulu_time_hours", 0)
        m = self._datarefs.get("sim/cockpit2/clock_timer/zulu_time_minutes", 0)
        s = self._datarefs.get("sim/cockpit2/clock_timer/zulu_time_seconds", 0)
        center_line(9, f"UTC {h:02d}:{m:02d}:{s:02d}", COLORS.WHITE, True)

        # Extra (version information)
        center_line(1, f"VERSION {winwing.version}", COLORS.CYAN, True)
        center_line(12, "github.com/devleaks", COLORS.DEFAULT, True)
        title = "/pywinwing"
        center_line(13, title, COLORS.DEFAULT, True)
        idx = title.index("g") + int((PAGE_CHARS_PER_LINE - len(title)) / 2)
        page[13][idx * PAGE_BYTES_PER_CHAR] = COLORS.RED

        return page
