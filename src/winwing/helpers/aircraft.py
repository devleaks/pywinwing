"""
"""

import os
import glob
import logging
import inspect

from abc import ABC
from typing import Tuple, Dict, Any, Set, List

from ruamel.yaml import YAML

from winwing.devices import WinwingDevice
from winwing.devices.mcdu import device

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

yaml = YAML(typ="safe", pure=True)

ACF_FILE_GLOB = "*.yaml"  # include .yml file if necessary


class Aircraft(ABC):

    AIRCRAFT_KEYS = []

    def __init__(self, author: str, icao: str, variant: str | None = None) -> None:
        self.author = author
        self.icao = icao
        self.variant = variant
        self._config = None

    @staticmethod
    def key(author: str, icao: str) -> str:
        return f"{icao}::{author}"

    @staticmethod
    def pretty_author(author: str) -> str:
        max_len = 20
        n = author
        if len(n) > max_len:
            i = n.rfind(" ", 0, max_len)
            if i > 0:
                n = n[:i]
            if len(n) < len(author):
                n = n + ".."
        return n

    @staticmethod
    def new(author: str, icao: str, extension_paths: List[str] = []):
        """Create aircraft for supplied (author, icao)

        If no device aircraft can be found, returns None

        Args:
            author (str): Author of aircraft
            icao (str): Aircraft ICAO

        Returns:
            [Aircraft]: Aircraft adapter
        """

        adapters = Aircraft.adapters()
        key = Aircraft.key(author=author, icao=icao)
        reqacf = list(filter(lambda x: key in x.AIRCRAFT_KEYS, adapters))
        logger.debug(f"aircraft adapters for {icao},{author}: {reqacf}")
        if len(reqacf) == 0:
            logger.warning(f"no aircraft adapter for {author}, {icao}")
            return None
        if len(reqacf) > 1:
            logger.warning(f"More than one aircraft adapter for {author}, {icao}: {reqacf}")
            return None
        adapter = reqacf[0]
        logger.info(f"aircraft adapter for {icao} by {author} is {adapter}")
        aircraft = adapter(author=author, icao=icao)
        aircrafts_data = Aircraft.list(extension_paths=extension_paths)
        if key not in aircrafts_data:
            logger.warning(f"no configuration data for {icao} by {author}")
        else:
            temp = aircrafts_data.get(key)
            aircraft._config = temp
            logger.info(f"configuration data set for {icao} by {author}")
        return aircraft

    @staticmethod
    def list(extension_paths: List[str] = []) -> Dict[Tuple[str, str], Dict]:
        aircrafts = {}
        path = os.path.join(os.path.dirname(__file__), "..", "assets")
        extension_paths.append(path)
        for folder in extension_paths:
            files = glob.glob(os.path.join(folder, "**", ACF_FILE_GLOB), recursive=True)
            for file in files:
                with open(file, "r") as fp:
                    data = yaml.load(fp)
                    if type(data) is dict:
                        author = data.get("author")
                        icao = data.get("icao")
                        if author is not None and icao is not None:
                            data["__filename__"] = file
                            aircrafts[Aircraft.key(author=author, icao=icao)] = data
        if len(aircrafts) == 0:
            logger.warning("no available aircraft")
            return {}

        def pretty(a):
            a = a.split("::")
            return f"{a[0]} by {Aircraft.pretty_author(a[1])}"

        logger.info(f"aircraft data provided for: {', '.join(f'{pretty(a)}' for a in aircrafts)}")
        return aircrafts

    @staticmethod
    def adapters() -> list:
        """Returns the list of all subclasses of Aircraft.

        Recurses through all sub-sub classes

        Returns:
            [list]: list of all Aircraft subclasses

        Raises:
            ValueError: If invalid class found in recursion (types, etc.)
        """
        subclasses = set()
        stack = []
        try:
            stack.extend(Aircraft.__subclasses__())
        except (TypeError, AttributeError) as ex:
            raise ValueError("Invalid class" + repr(Aircraft)) from ex
        while stack:
            sub = stack.pop()
            if not inspect.isabstract(sub):
                subclasses.add(sub)
            else:
                logger.debug(f"is abstract {sub}")
            try:
                stack.extend(s for s in sub.__subclasses__() if s not in subclasses)
            except (TypeError, AttributeError):
                continue
        logger.info(f"aircaft adapters {subclasses}")
        return list(subclasses)

    @classmethod
    def load_from_data(cls, data):
        author = data.get("author")
        icao = data.get("icao")
        a = Aircraft.new(author=author, icao=icao)
        # If using a config file, aircraft will be found, but no data attached to it
        # Data is added here.
        if a is not None:
            a._config = data
            v = data.get("variant")
            if v is not None:
                a.variant = v
            return a
        logger.warning(f"cannot create aircraft for {icao}, {author}")
        return None

    @classmethod
    def load_from_file(cls, filename):
        if not os.path.exists(filename):
            logger.error(f"aircraft file {filename} not found")
            return None
        try:
            with open(filename, "r") as fp:
                config = yaml.load(fp)
            return Aircraft.load_from_data(data=config)
        except:
            logger.warning(f"cannot load aircraft configuration file {filename}")

    @property
    def loaded(self) -> bool:
        return self._config is not None

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

    def config_filename(self, prefix: str, extension: str = ".yaml"):
        d = os.path.dirname(__file__)
        fn = f"{prefix}_{self.author}_{self.icao}"
        if self.variant is not None:
            fn = fn + f"_{self.variant}"
        fn = os.path.join(d, "..", "assets", fn + extension)
        logger.debug(f"loaded {os.path.abspath(fn)}")
        return os.path.abspath(fn)

    def load(self, prefix: str = ""):
        fn = self.config_filename(prefix=prefix, extension="_new.yaml")
        print(">>>>>>>>>>>>>>>>>", fn)
        if not os.path.exists(fn):
            logger.warning(f"aircraft file {fn} not found")
            return
        with open(fn, "r") as fp:
            self._config = yaml.load(fp)

    def display_datarefs(self) -> Set[str]:
        """Returns datarefs necessary to drive entire display content

        Returns

            List[str]: list of datarefs used for display


        """
        if not self.loaded:
            return set()
        device_reports = self._config.get("simulator-reports", [])
        datarefs = [d["simulator-value-name"] for d in device_reports if d["report-type"] == "simulator-value-change" and d["action"] == "refresh-display"]
        # print("DISPLAY DREFS", datarefs)
        return set(datarefs)

    def datarefs(self) -> Set[str]:
        """Returns accessoriy datarefs for other purposes

        Returns

            List[str]: list of datarefs used for display


        """
        if not self.loaded:
            return set()
        device_reports = self._config.get("simulator-reports", [])
        datarefs = [d["simulator-value-name"] for d in device_reports if d["report-type"] == "simulator-value-change"]
        # print("ALL DREFS", datarefs)
        return set(datarefs)

    def device_reports(self) -> List:
        """Returns key mapping.

        Supplied information is sufficient to perform necessary action for key.

        Returns

            List[Dict]:

        """
        if not self.loaded:
            return {}
        return self._config.get("device-reports", [])

    def simulator_reports(self) -> List:
        """Returns simulator feedback for device handling.

        Supplied information is sufficient to perform necessary action for key.

        Returns

            List[Dict]:

        """
        if not self.loaded:
            return {}
        return self._config.get("simulator-reports", [])
