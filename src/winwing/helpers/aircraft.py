"""Abstract base class for representation of an aircraft to Winwing devices

A winwing device may often be used by different aircrafts.
However, each aircraft, from different editors, may have different means to operate and do things in the simulator.
This class aims at hiding those particularities behind a common representation.

"""

import os
import glob
import logging
import inspect

from abc import ABC
from time import sleep
from typing import Tuple, Dict, Set, List

from ruamel.yaml import YAML

from winwing.devices import WinwingDevice


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

yaml = YAML(typ="safe", pure=True)

ACF_FILE_GLOB = "*.yaml"  # include .yml file if necessary


class Aircraft(ABC):

    AIRCRAFT_KEYS = []

    def __init__(self, author: str, icao: str, variant: str = "") -> None:
        self._ready = False
        self.author = author
        self.icao = icao
        self._variant = variant
        self._config = None

    @staticmethod
    def key(author: str, icao: str, variant: str = "") -> str:
        return f"{icao}:{variant}:{author}"

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
    def new(author: str, icao: str, variant: str = "", extension_paths: List[str] = []):
        """Create aircraft for supplied (author, icao)

        If no device aircraft can be found, returns None

        Args:
            author (str): Author of aircraft
            icao (str): Aircraft ICAO

        Returns:
            (Aircraft): Aircraft adapter
        """

        adapters = Aircraft.adapters()
        key = Aircraft.key(author=author, icao=icao, variant=variant)
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
                        variant = data.get("variant", "")
                        if author is not None and icao is not None:
                            data["__filename__"] = file
                            aircrafts[Aircraft.key(author=author, icao=icao, variant=variant)] = data
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
        variant = data.get("variant", "")
        a = Aircraft.new(author=author, icao=icao, variant=variant)
        # If using a config file, aircraft will be found, but no data attached to it
        # Data is added here.
        if a is not None:
            a._config = data
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
            logger.warning(f"cannot load aircraft configuration file {filename}", exc_info=True)

    @property
    def loaded(self) -> bool:
        return self._config is not None

    def init(self, device: WinwingDevice) -> bool:
        """Convenience function that can be used to adjust aircraft properties
           depending on device and/or API used

        Args:
            device (WinwingDevice): [description]

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
        """Returns all datarefs used by this aircraft configuration and that may be requested to the simulator

        Returns

            List[str]: list of all datarefs used by this configuration


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

    #
    # Aircraft Variant Management
    # Aircraft variants have the same ICAO and author but have different options
    # or add-on available that change the behavior of the aircraft.
    #
    @property
    def variant(self) -> str:
        return self._variant

    @variant.setter
    def variant(self, variant):
        self._variant = variant

    def same_variant(self, variant) -> bool:
        """Compare two aicraft variants if they are set.

        If one if not set, returns that they are equivalent.

        returns:

        (bool): Aircraft variants equivalence

        """
        if variant is None or self.variant is None:
            return True
        return self.variant == variant

    def variant_datarefs(self) -> Set[str]:
        """Returns list of datarefs necessary for variant determination.

        returns
            (Set): List of datarefs necessary for variant determination
        """
        return set(["sim/cockpit2/clock_timer/zulu_time_hours"])

    def variant_key(self) -> str:
        """Build variant string from variant dataref values

        This allows to inspect one or more datarefs and determine the aicraft
        variant from those datarefs.

        returns:
            (str): Variant identification
        """
        return ""

    def wait_for_aircraft_variant(self, api):
        """Wait for value of aicraft variant datarefs
        """
        vdrefs = self.variant_datarefs()
        if len(vdrefs) == 0:
            logger.info("aicraft has not variant")
            return
        api.register_datarefs(paths=self.variant_datarefs())
        if not self._ready:
            api.display.message("waiting for aircraft variant...")
        variant = self.variant_key()
        key = Aircraft.key(author=self.author, icao=self.icao, variant=variant)
        warning_count = 0
        if key not in api.VALID_AIRCRAFTS:
            while key not in api.VALID_AIRCRAFTS:
                if warning_count <= MAX_WARNING_COUNT:
                    last_warning = " (last warning)" if warning_count == MAX_WARNING_COUNT else ""
                    logger.warning(f"waiting for valid aircraft (current {key} not in list {api.VALID_AIRCRAFTS.keys()}{last_warning}")
                warning_count = warning_count + 1
                sleep(2)
                variant = self.variant_key()
                key = Aircraft.key(author=self.author, icao=self.icao, variant=variant)
        self.variant = variant
        logger.info(f"{self.author} {self.icao} {self.variant} detected")
        # no change to status lights, we still need the data