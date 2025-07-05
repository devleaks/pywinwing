"""
"""
import logging
import re
from typing import Set

from winwing.helpers.aircraft import Aircraft
from .constant import (
    MCDU_TERM_COLORS,
    PAGE_LINES,
    PAGE_BYTES_PER_CHAR,
    PAGE_BYTES_PER_LINE,
)

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


MCDU_DISPLAY_DATA = "AirbusFBW/MCDU(?P<unit>[1-3]+)(?P<name>(title|stitle|label|cont|scont|sp)+)(?P<line>[1-6]*)(?P<large>[L]*)(?P<color>[abgmswy]+)"


class ToLissAircraft(Aircraft):

    AIRCRAFT_KEYS = [
        Aircraft.key(icao="A321", author="Gliding Kiwi"),
        Aircraft.key(icao="A21N", author="Gliding Kiwi"),
        Aircraft.key(icao="A339", author="GlidingKiwi"),
        Aircraft.key(icao="A359", author="FlightFactor and ToLiss"),
    ]

    def __init__(self, author: str, icao: str, variant: str | None = None) -> None:
        Aircraft.__init__(self, author=author, icao=icao, variant=variant)

        self._datarefs = {}
        self.lines = {}

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
            if line == "L":
                line = dataref[-3]
            if "label" in dataref:
                self.update_label(dataref=dataref, value=value, mcdu_unit=mcdu_unit, line=line)
            else:
                self.update_line(dataref=dataref, value=value, mcdu_unit=mcdu_unit, line=line)

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
        self.lines[f"AirbusFBW/MCDU{mcdu_unit}label{line}"] = self.get_line(mcdu_unit=mcdu_unit, line=line, what=["label"], colors=MCDU_TERM_COLORS)[0]

    def update_line(self, dataref: str, value, mcdu_unit: int, line: int):
        lines = self.get_line(mcdu_unit=mcdu_unit, line=line, what=["cont", "scont"], colors=MCDU_TERM_COLORS)
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
                            has_char.append((v[c], color))
                if len(has_char) == 1:
                    this_line = this_line + has_char
                else:
                    # if len(has_char) > 1:
                    #     logger.debug(f"mutiple char {code}, {c}: {has_char}")
                    this_line.append((" ", "w"))
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
                            has_char.append((v[c], color))
                if len(has_char) == 1:
                    this_line = this_line + has_char
                else:
                    # if len(has_char) > 1:
                    #     logger.debug(f"mutiple char {code}, {c}: {has_char}")
                    this_line.append((" ", "w"))
            lines.append(this_line)
        return lines

    def show_page(self, mcdu_unit) -> list:
        page = [[" " for _ in range(PAGE_BYTES_PER_LINE)] for _ in range(PAGE_LINES)]

        def show_line(line, lnum, font_small):
            pos = 0
            for c in line:
                if c[1] == "s":  # "special" characters (rev. eng.)
                    if c[0] == "0":
                        c = (chr(60), "b")
                    elif c[0] == "1":
                        c = (chr(62), "b")
                    elif c[0] == "2":
                        c = (chr(60), "w")
                    elif c[0] == "3":
                        c = (chr(62), "w")
                    elif c[0] == "4":
                        c = (chr(60), "a")
                    elif c[0] == "5":
                        c = (chr(62), "a")
                    elif c[0] == "A":
                        c = (chr(91), "b")
                    elif c[0] == "B":
                        c = (chr(93), "b")
                    elif c[0] == "E":
                        c = (chr(35), "a")
                page[lnum][pos * PAGE_BYTES_PER_CHAR] = c[1]  # color
                page[lnum][pos * PAGE_BYTES_PER_CHAR + 1] = font_small
                page[lnum][pos * PAGE_BYTES_PER_CHAR + 2] = c[0]  # char
                pos = pos + 1

        logger.debug(f"page for mcdu unit {mcdu_unit}")

        show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}title"], 0, 0)
        for l in range(1, 7):
            show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}label{l}"], 2 * l - 1, 1)
            show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}cont{l}"], 2 * l, 0)
        show_line(self.lines[f"AirbusFBW/MCDU{mcdu_unit}sp"], 13, 0)

        return page
