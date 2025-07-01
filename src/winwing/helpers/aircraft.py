"""
"""

import os
import logging

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Set

from ruamel.yaml import YAML

from winwing.devices.winwing import WinwingDevice

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

yaml = YAML(typ="safe", pure=True)


class Aircraft(ABC):

    def __init__(self, vendor: str, icao: str, variant: str | None = None) -> None:
        self.vendor = vendor
        self.icao = icao
        self.variant = variant
        self._config = None

    @classmethod
    def load_from_file(cls, filename):
        if not os.path.exists(filename):
            logger.warning(f"aircraft file {filename} not found")
            return
        with open(filename, "r") as fp:
            config = yaml.load(fp)
        a = cls(vendor=config.get("vendor"), icao=config.get("icao"))
        a._config = config
        v = config.get("variant")
        if v is not None:
            a.variant = v
        return a

    def config_filename(self, prefix: str, extension: str = ".yaml"):
        d = os.path.dirname(__file__)
        fn = f"{prefix}_{self.vendor}_{self.icao}"
        if self.variant is not None:
            fn = fn + f"_{self.variant}"
        fn = os.path.join(d, "..", "assets", fn + extension)
        logger.debug(f"loaded {os.path.abspath(fn)}")
        return os.path.abspath(fn)

    def load(self, prefix: str):
        fn = self.config_filename(prefix=prefix)
        if not os.path.exists(fn):
            logger.warning(f"aircraft file {fn} not found")
            return
        with open(fn, "r") as fp:
            self._config = yaml.load(fp)

    def required_datarefs(self) -> Set[str]:
        """Returns datarefs necessary to drive entire display content

        Returns

            List[str]: list of datarefs used for display


        """
        datarefs = self._config.get("display-datarefs", [])
        return set(datarefs)

    def datarefs(self) -> Set[str]:
        """Returns accessoriy datarefs for other purposes

        Returns

            List[str]: list of datarefs used for display


        """
        datarefs = self._config.get("display-datarefs", [])
        datarefs.extend(self._config.get("datarefs", []))
        return set(datarefs)

    def mapped_keys(self) -> Dict[str, Any]:
        """Returns key ampping.

        Supplied information is sufficient to perform necessary action for key.

        Returns

            Dict[str, Any]: {key: data} for key, with data necessary to carry over actions when key pressed/released

        """
        keys = self._config.get("keys", {})
        return keys

    def init(self, device: WinwingDevice) -> bool:
        """Convenience function that can be used to adjust aircraft properties
           depending on device and/or API used

        Args:
            device (WinwingDevice): [description]
            api (XPAPI): [description]

        Returns:
            bool: success of initialisation
        """
        return True
