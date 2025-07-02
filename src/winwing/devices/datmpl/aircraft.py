"""
"""

from typing import List

from winwing.helpers.aircraft import Aircraft


class DAAircraft(Aircraft):
    """Winwing Device Adapter aircraft specifics.

    Loads and share aicraft specifics: datarefs, commands, values to set, etc.
    """

    def __init__(self, vendor: str, icao: str, variant: str | None = None) -> None:
        Aircraft.__init__(self, vendor=vendor, icao=icao, variant=variant)
