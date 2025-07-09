"""
"""

from abc import abstractmethod
import logging
from typing import Set

from winwing.helpers.aircraft import Aircraft
from .constant import (
    PAGE_LINES,
    PAGE_BYTES_PER_LINE,
)

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class MCDUAircraft(Aircraft):
    """Aircraft with MCDU-specific requirements.

    Abstract functions in this class are used by MCDU class.

    """

    def __init__(self, author: str, icao: str, variant: str | None = None) -> None:
        Aircraft.__init__(self, author=author, icao=icao, variant=variant)

    @property
    def mcdu_units(self) -> Set[int]:
        if not self.loaded:
            return set()
        return set(self._config.get("mcdu-units", []))

    @staticmethod
    def is_display_dataref(dataref: str) -> bool:
        return False

    @abstractmethod
    def get_mcdu_unit(self, dataref) -> int:
        return 0

    @abstractmethod
    def set_mcdu_unit(self, str_in: str, mcdu_unit: int):
        return str_in

    @abstractmethod
    def variable_changed(self, dataref: str, value):
        pass

    def encode_bytes(self, dataref, value) -> str | bytes:
        try:
            return value.decode("ascii").replace("\u0000", "")
        except:
            logger.warning(f"cannot decode bytes for {dataref.name} (encoding=ascii)", exc_info=True)
        return value

    def show_page(self, mcdu_unit) -> list:
        return [[" " for _ in range(PAGE_BYTES_PER_LINE)] for _ in range(PAGE_LINES)]
