"""
"""

import logging
import re
from typing import Set

from .mcdu_aircraft import MCDUAircraft
from .device import SPECIAL_CHARACTERS
from .constant import (
    COLORS,
    PAGE_CHARS_PER_LINE,
    PAGE_LINES,
    PAGE_BYTES_PER_CHAR,
    PAGE_BYTES_PER_LINE,
)


TOLISS_MCDU_LINE_COLOR_CODES = [
    "a",  # amber, dark yellow
    "b",
    "g",
    "m",
    "w",
    "y",
    "s",  # special characters, not a color
    "Lw",  # bold white, bright white
    "Lg",  # bold white, bright green
]

COLORS_BY_MCDU_COLOR_KEY = {c.key: c for c in COLORS}

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


MCDU_DISPLAY_DATA = "AirbusFBW/MCDU(?P<unit>[1-3]+)(?P<name>(title|stitle|label|cont|scont|sp)+)(?P<line>[1-6]*)(?P<large>[L]*)(?P<color>[abgmswy]+)"


class ToLissAircraft(MCDUAircraft):

    AIRCRAFT_KEYS = [
        MCDUAircraft.key(icao="A321", author="Gliding Kiwi"),
        MCDUAircraft.key(icao="A21N", author="Gliding Kiwi"),
        MCDUAircraft.key(icao="A339", author="GlidingKiwi"),
        MCDUAircraft.key(icao="A359", author="FlightFactor and ToLiss"),
    ]

    def __init__(self, author: str, icao: str, variant: str | None = None) -> None:
        MCDUAircraft.__init__(self, author=author, icao=icao, variant=variant)

        self._datarefs = {}
        self.lines = {}

    @property
    def mcdu_units(self) -> Set[int]:
        if not self.loaded:
            return set()
        return set(self._config.get("mcdu-units", []))

    @staticmethod
    def is_display_dataref(dataref: str) -> bool:
        if "VertSlewKeys" in dataref:
            return True
        return re.match(MCDU_DISPLAY_DATA, dataref) is not None

    def get_mcdu_unit(self, dataref) -> int:
        mcdu_unit = -1
        try:
            m = None
            if "VertSlewKeys" in dataref:
                m = re.match("AirbusFBW/MCDU(?P<unit>[1-3]+)VertSlewKeys", dataref)
            else:
                m = re.match(MCDU_DISPLAY_DATA, dataref)
            if m is None:
                logger.warning(f"not a display dataref {dataref}")
                return -1
            mcdu_unit = int(m["unit"])
        except:
            logger.warning(f"error invalid MCDU unit for {dataref}")
            return -1
        return mcdu_unit

    def set_mcdu_unit(self, str_in: str, mcdu_unit: int):
        if mcdu_unit == 2:
            return re.sub(r"MCDU[123]", "MCDU2", str_in)
        elif mcdu_unit == 3:
            return re.sub(r"MCDU[123]", "MCDU3", str_in)
        return str_in if "MCDU1" in str_in else re.sub(r"MCDU[123]", "MCDU1", str_in)

    def clear_lines(self):
        self.lines = {}

    def variable_changed(self, dataref: str, value):
        self._datarefs[dataref] = value
        mcdu_unit = self.get_mcdu_unit(dataref)

        if mcdu_unit not in self.mcdu_units:
            logger.warning(f"invalid MCDU unit {mcdu_unit} ({self.mcdu_units})")
            return

        if "title" in dataref:
            self.update_title(dataref=dataref, value=value, mcdu_unit=mcdu_unit)
        elif "sp" in dataref:
            self.update_sp(dataref, value, mcdu_unit=mcdu_unit)
        else:
            line = dataref[-2]
            if line == "L":  # "color" Lg, Lw
                line = dataref[-3]
            if "label" in dataref:
                self.update_label(dataref=dataref, value=value, mcdu_unit=mcdu_unit, line=line)
            else:
                self.update_line(dataref=dataref, value=value, mcdu_unit=mcdu_unit, line=line)

    def encode_bytes(self, dataref, value) -> str | bytes:
        try:
            return value.decode("ascii").replace("\u0000", "")
        except:
            logger.warning(f"cannot decode bytes for {dataref.name} (encoding=ascii)", exc_info=True)
        return value

    def combine(self, l1, l2):
        line = []
        for i in range(24):
            if l1[i][0] == " ":
                line.append(l2[i])
                continue
            # if l2[i][0] != " ":
            #     logger.debug(f"2 chars {l1[i]} / {l2[i]}")
            line.append(l1[i])
        return line

    def update_title(self, dataref: str, value, mcdu_unit: int):
        lines = self.get_line_extra(mcdu_unit=mcdu_unit, what=["title", "stitle"], colors="bgwys")
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}title"] = self.combine(lines[0], lines[1])

    def update_sp(self, dataref: str, value, mcdu_unit: int):
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}sp"] = self.get_line_extra(mcdu_unit=mcdu_unit, what=["sp"], colors="aw")[0]

    def update_label(self, dataref: str, value, mcdu_unit: int, line: int):
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}label{line}"] = self.get_line(mcdu_unit=mcdu_unit, line=line, what=["label"], colors=TOLISS_MCDU_LINE_COLOR_CODES)[0]

    def update_line(self, dataref: str, value, mcdu_unit: int, line: int):
        lines = self.get_line(mcdu_unit=mcdu_unit, line=line, what=["cont", "scont"], colors=TOLISS_MCDU_LINE_COLOR_CODES)
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}cont{line}"] = self.combine(lines[0], lines[1])

    def get_line_extra(self, mcdu_unit, what, colors):
        lines = []
        for code in what:
            this_line = []
            for c in range(24):
                has_char = []
                for color in colors:
                    if code == "stitle" and color == "s":  # if code in ["stitle", "title"] and color == "s":
                        continue
                    name = f"AirbusFBW/MCDU{mcdu_unit}{code}{color}"
                    v = self._datarefs.get(name)
                    if v is None:
                        # logger.debug(f"no value for dataref {name}")
                        continue
                    if c < len(v):
                        if v[c] != " ":
                            if color in COLORS_BY_MCDU_COLOR_KEY:
                                has_char.append((v[c], COLORS_BY_MCDU_COLOR_KEY[color]))
                            else:
                                has_char.append((v[c], color))
                if len(has_char) == 1:
                    this_line = this_line + has_char
                else:
                    # if len(has_char) > 1:
                    #     logger.debug(f"mutiple char {code}, {c}: {has_char}")
                    this_line.append((" ", COLORS.WHITE))
            lines.append(this_line)
        return lines

    def get_line(self, mcdu_unit: int, line: int, what: list, colors):
        lines = []
        for code in what:
            this_line = []
            for c in range(24):
                has_char = []
                for color in colors:
                    if code.endswith("cont") and color.startswith("L"):
                        continue
                    name = f"AirbusFBW/MCDU{mcdu_unit}{code}{line}{color}"
                    v = self._datarefs.get(name)
                    if v is None:
                        # logger.debug(f"no value for dataref {name}")
                        continue
                    if c < len(v):
                        if v[c] != " ":
                            if color in COLORS_BY_MCDU_COLOR_KEY:
                                has_char.append((v[c], COLORS_BY_MCDU_COLOR_KEY[color]))
                            else:
                                has_char.append((v[c], color))
                if len(has_char) == 1:
                    this_line = this_line + has_char
                else:
                    # if len(has_char) > 1:
                    #     logger.debug(f"mutiple char {code}, {c}: {has_char}")
                    this_line.append((" ", COLORS.WHITE))
            lines.append(this_line)
        return lines

    def show_page(self, mcdu_unit) -> list:
        COLORS_BY_KEY = {c.key: c for c in COLORS}
        page = [[" " for _ in range(PAGE_BYTES_PER_LINE)] for _ in range(PAGE_LINES)]

        def show_line(line, lnum, font_small):
            if line is None:
                logger.warning(f"line {lnum} is empty, replacing by blank line")
                line = [(" ", COLORS.WHITE) for i in range(PAGE_CHARS_PER_LINE)]
            pos = 0
            for c in line:
                # this is for (s)pecial color (codes?)
                if type(c[1]) is str and c[1] == "s":  # "special" characters (rev. eng.)
                    if c[0] == "0":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_LEFT.value), COLORS.CYAN)
                    elif c[0] == "1":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_RIGHT.value), COLORS.CYAN)
                    elif c[0] == "2":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_LEFT.value), COLORS.WHITE)
                    elif c[0] == "3":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_RIGHT.value), COLORS.WHITE)
                    elif c[0] == "4":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_LEFT.value), COLORS.AMBER)
                    elif c[0] == "5":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_RIGHT.value), COLORS.AMBER)
                    elif c[0] == "A":
                        c = (chr(SPECIAL_CHARACTERS.SQUARE_BRACKET_OPEN.value), COLORS.CYAN)
                    elif c[0] == "B":
                        c = (chr(SPECIAL_CHARACTERS.SQUARE_BRACKET_CLOSE.value), COLORS.CYAN)
                    elif c[0] == "E":
                        c = (chr(SPECIAL_CHARACTERS.SQUARE.value), COLORS.AMBER)
                # this is for "all" color
                if c[0] == "`":
                    c = (chr(SPECIAL_CHARACTERS.DEGREE.value), c[1])
                color = c[1]
                if type(color) is str:
                    logger.warning(f"invalid color {color}, line={[c[0] for c in line]} substituing default color")
                    color = COLORS.DEFAULT
                page[lnum][pos * PAGE_BYTES_PER_CHAR] = color
                page[lnum][pos * PAGE_BYTES_PER_CHAR + 1] = font_small
                page[lnum][pos * PAGE_BYTES_PER_CHAR + 2] = c[0]  # char
                pos = pos + 1

        logger.debug(f"page for mcdu unit {mcdu_unit}")

        show_line(self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}title"), 0, 0)
        for l in range(1, 7):
            show_line(self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}label{l}"), 2 * l - 1, 1)
            show_line(self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}cont{l}"), 2 * l, 0)
        show_line(self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}sp"), 13, 0)

        # Additional, non printed keys in lower right corner of display
        vertslew_dref = self.set_mcdu_unit(str_in="AirbusFBW/MCDU1VertSlewKeys", mcdu_unit=mcdu_unit)
        vertslew_key = self._datarefs.get(self.set_mcdu_unit(str_in="AirbusFBW/MCDU1VertSlewKeys", mcdu_unit=mcdu_unit))
        if vertslew_key == 1 or vertslew_key == 2:
            c = (PAGE_CHARS_PER_LINE - 2) * PAGE_BYTES_PER_CHAR
            page[PAGE_LINES - 1][c] = COLORS.WHITE
            page[PAGE_LINES - 1][c + 1] = False
            page[PAGE_LINES - 1][c + 2] = chr(SPECIAL_CHARACTERS.ARROW_UP.value)
        if vertslew_key == 1 or vertslew_key == 3:
            c = (PAGE_CHARS_PER_LINE - 1) * PAGE_BYTES_PER_CHAR
            page[PAGE_LINES - 1][c] = COLORS.WHITE
            page[PAGE_LINES - 1][c + 1] = False
            page[PAGE_LINES - 1][c + 2] = chr(SPECIAL_CHARACTERS.ARROW_DOWN.value)

        return page
