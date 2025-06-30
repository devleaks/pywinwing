"""
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from pywinwing.device import WinwingDevice
from pywinwing.helpers import XPAPI


class Aircraft(ABC):

    def __init__(self, icao: str) -> None:
        self.icao = icao
        self._config = None

    def load(self, filename):
        with open(filename, "r") as fp:
            self._config = fp.read()

    @abstractmethod
    def display_datarefs(self) -> List[str]:
        """Returns datarefs necessary to drive entire display content

        Returns

            List[str]: list of datarefs used for display


        """
        datarefs = []
        return datarefs

    @abstractmethod
    def other_datarefs(self) -> List[str]:
        """Returns accessoriy datarefs for other purposes

        Returns

            List[str]: list of datarefs used for display


        """
        datarefs = []
        return datarefs

    @abstractmethod
    def mapped_keys(self) -> Dict[str, Any]:
        """Returns key ampping.

        Supplied information is sufficient to perform necessary action for key.

        Returns

            Dict[str, Any]: {key: data} for key, with data necessary to carry over actions when key pressed/released

        """
        keys = {}
        return keys

    def init(self, device: WinwingDevice, api: XPAPI) -> bool:
        """Convenience function that can be used to adjust aircraft properties
           depending on device and/or API used

        Args:
            device (WinwingDevice): [description]
            api (XPAPI): [description]

        Returns:
            bool: success of initialisation
        """
        return True
