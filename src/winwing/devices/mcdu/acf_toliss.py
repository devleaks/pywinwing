"""Aircraft class for ToLiss Airbus aircraft, probably all of them.

This Aircraft class is completed with one aircraft configuration file for each Airbus
model (A321, A330, etc.).
The configuration file list datarefs and commands used by/for each aircraft.

"""

import logging
import re
from typing import Set, List

from winwing.devices import mcdu

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
    "Lw",  # large white
    "Lg",  # large green
]
# notes:
# First "title" line is Large font, there are then alternate "label" line (small font) and content line (Large font (cont) AND small font (scont)).
# Lg, Lw are Large font, white or green, used on line with small fonts (like "label" lines)
# Lines with both large and small fonts are "combined" into a single line, in case there is a char in Large it has precedence on a char in small.
# "sp" lines (color w or a) is last prompt line, always Large font.
# Color "s" is special characters, coded, coding includes both the glyph and the color, example: code '4' is amber left arrow.
# Special characters are treated towards the end, being replaced by actual glyphs.
# Letters are mostly (exclusively?) UPPER case, only their sizes varies.

COLORS_BY_MCDU_COLOR_KEY = {c.key: c for c in COLORS}

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


MCDU_DISPLAY_DATA = r"AirbusFBW/MCDU(?P<unit>[1-3])(?P<name>(title|stitle|sp|label|cont|scont))(?P<line>[1-6]?)(?P<color>(Lw|Lg|[abgmswy]))"


class ToLissAirbus(MCDUAircraft):

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
        if dataref == "AirbusFBW/DUBrightness[6]":  # MCDU screen brightness unit 1
            return 1
        elif dataref == "AirbusFBW/DUBrightness[7]":  # MCDU screen brightness unit 2
            return 2
        try:
            m = None
            if "VertSlewKeys" in dataref:
                m = re.match("AirbusFBW/MCDU(?P<unit>[1-3])VertSlewKeys", dataref)
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
        if str_in.startswith("AirbusFBW/DUBrightness"):
            if mcdu_unit == 1:
                return "AirbusFBW/DUBrightness[6]"
            elif mcdu_unit == 2:
                return "AirbusFBW/DUBrightness[7]"
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

        m = re.match(MCDU_DISPLAY_DATA, dataref)
        if m is None:
            logger.debug(f"not a display dataref {dataref}")
            return

        colors = TOLISS_MCDU_LINE_COLOR_CODES
        line = -1
        what = m.group("name")
        if what.endswith("title"):  # stitle, title
            colors = "bgwys"
        elif what == "sp":
            colors = "aw"
        else:  # label, scont, cont
            line = int(m.group("line"))
        self.update_line(mcdu_unit=mcdu_unit, line=line, what=what, colors=colors)

    def encode_bytes(self, dataref, value) -> str | bytes:
        try:
            return value.decode("ascii").replace("\u0000", "")
        except:
            logger.warning(f"cannot decode bytes for {dataref.name} (encoding=ascii)", exc_info=True)
        return value

    def update_line(self, mcdu_unit: int, line: int, what: str, colors):
        """Line is 24 characters, 1 character is (<char>, <color>, <small>)."""
        line_str = "" if line == -1 else str(line)
        this_line = []
        for c in range(24):
            has_char = []
            size = 1 if what in ["stitle", "scont", "label"] else 0
            for color in colors:
                if what.endswith("cont") and color.startswith("L"):
                    continue
                if size == 1 and color.startswith("L"):  # small becomes large
                    size = 0
                name = f"AirbusFBW/MCDU{mcdu_unit}{what}{line_str}{color}"
                v = self._datarefs.get(name)
                if v is None:
                    # logger.debug(f"no value for dataref {name}")
                    continue
                if c < len(v):
                    if v[c] != " ":
                        if color.startswith("L") and len(color) == 2:  # maps Lg, Lw to g, w.
                            color = color[1]  # prevents "invalid color" further on
                        if color in COLORS_BY_MCDU_COLOR_KEY:
                            has_char.append((v[c], COLORS_BY_MCDU_COLOR_KEY[color], size))
                        else:
                            has_char.append((v[c], color, size))
            if len(has_char) == 1:
                this_line = this_line + has_char
            else:
                # if len(has_char) > 1:
                #     logger.debug(f"mutiple char {what}, {c}: {has_char}")
                this_line.append((" ", COLORS.WHITE, size))
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}{what}{line_str}"] = this_line

    def show_page(self, mcdu_unit) -> list:
        """Adjusts for special characters"""
        page = [[" " for _ in range(PAGE_BYTES_PER_LINE)] for _ in range(PAGE_LINES)]

        def combine(lr, sm):
            return [sm[i] if lr[i][0] == " " else lr[i] for i in range(PAGE_CHARS_PER_LINE)]

        def show_line(line, lnum):
            if line is None:
                logger.warning(f"line {lnum} is empty, replacing by blank line")
                line = [(" ", COLORS.WHITE) for i in range(PAGE_CHARS_PER_LINE)]
            pos = 0
            for c in line:
                # this is for (s)pecial color (codes?)
                if len(c) != 3:
                    logger.warning(f"invalid character {c}, replaced by white space")
                    c = (" ", COLORS.WHITE, 0)
                if type(c[1]) is str and c[1] == "s":  # "special" characters (rev. eng.)
                    if c[0] == "0":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_LEFT.value), COLORS.CYAN, c[2])
                    elif c[0] == "1":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_RIGHT.value), COLORS.CYAN, c[2])
                    elif c[0] == "2":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_LEFT.value), COLORS.WHITE, c[2])
                    elif c[0] == "3":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_RIGHT.value), COLORS.WHITE, c[2])
                    elif c[0] == "4":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_LEFT.value), COLORS.AMBER, c[2])
                    elif c[0] == "5":
                        c = (chr(SPECIAL_CHARACTERS.ARROW_RIGHT.value), COLORS.AMBER, c[2])
                    elif c[0] == "A":
                        c = (chr(SPECIAL_CHARACTERS.SQUARE_BRACKET_OPEN.value), COLORS.CYAN, c[2])
                    elif c[0] == "B":
                        c = (chr(SPECIAL_CHARACTERS.SQUARE_BRACKET_CLOSE.value), COLORS.CYAN, c[2])
                    elif c[0] == "E":
                        c = (chr(SPECIAL_CHARACTERS.SQUARE.value), COLORS.AMBER, c[2])
                # this is for "all" color
                if c[0] == "`":
                    c = (chr(SPECIAL_CHARACTERS.DEGREE.value), c[1], c[2])
                color = c[1]
                if type(color) is str:
                    logger.warning(f"invalid color {color}, line={[c[0] for c in line]} substituing default color")
                    color = COLORS.DEFAULT
                page[lnum][pos * PAGE_BYTES_PER_CHAR] = color
                page[lnum][pos * PAGE_BYTES_PER_CHAR + 1] = c[2]  # size 0=Large, 1=small
                page[lnum][pos * PAGE_BYTES_PER_CHAR + 2] = c[0]  # char
                pos = pos + 1

        logger.debug(f"page for mcdu unit {mcdu_unit}")

        line = combine(self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}title"), self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}stitle"))
        show_line(line, 0)
        for l in range(1, 7):
            show_line(self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}label{l}"), 2 * l - 1)
            line = combine(self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}cont{l}"), self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}scont{l}"))
            show_line(line, 2 * l)
        show_line(self.lines.get(f"AirbusFBW/MCDU{mcdu_unit}sp"), 13)

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

    def simulator_reports(self) -> List:
        """Returns simulator feedback for device handling.

        Supplied information is sufficient to perform necessary action for key.

        Returns

            List[Dict]:

        """
        if not self.loaded:
            return {}
        simulator_reports = self._config.get("simulator-reports", [])
        newrpts = []
        for sim_report in simulator_reports:
            if sim_report.get("report-type", "") == "simulator-value-change":
                dref = sim_report.get("simulator-value-name", "")
                if ToLissAirbus.is_display_dataref(dref):
                    for unit in self.mcdu_units:
                        if unit == 1:  # assumes config use MCDU unit 1...
                            continue
                        add_report = sim_report.copy()
                        add_report["simulator-value-name"] = self.set_mcdu_unit(str_in=dref, mcdu_unit=unit)
                        newrpts.append(add_report)
        return simulator_reports + newrpts
