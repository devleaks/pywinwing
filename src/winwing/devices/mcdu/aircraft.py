"""
"""
from typing import List

from winwing.helpers.aircraft import Aircraft


class MCDUAircraft(Aircraft):

    def __init__(self, vendor: str, icao: str, variant: str | None = None) -> None:
        Aircraft.__init__(self, vendor=vendor, icao=icao, variant=variant)
        self.load(prefix="MCDU")

    @property
    def mcdu_units(self) -> List[int]:
        return self._config.get("mcdu-units", [])