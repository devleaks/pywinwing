"""
"""

import re
from typing import List

from winwing.helpers.aircraft import Aircraft

MCDU_DISPLAY_DATA = "AirbusFBW/MCDU(?P<unit>[1-3]+)(?P<name>(title|stitle|label|cont|scont|sp)+)(?P<line>[1-6]*)(?P<large>[L]*)(?P<color>[abgmswy]+)"


class MCDUAircraft(Aircraft):

    def __init__(self, vendor: str, icao: str, variant: str | None = None) -> None:
        Aircraft.__init__(self, vendor=vendor, icao=icao, variant=variant)
        self.load(prefix="MCDU")

    @property
    def mcdu_units(self) -> List[int]:
        return self._config.get("mcdu-units", [])

    @staticmethod
    def is_display_dataref(dataref: str) -> bool:
        return re.match(MCDU_DISPLAY_DATA, dataref) is not None
