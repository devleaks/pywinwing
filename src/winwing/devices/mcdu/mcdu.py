"""Winwing MCDU Device as a while

Global management of the device, hardware interaction,
communication with simulator, dealing with different types of Airbus aircrafts...

"""

from __future__ import annotations
import io
import logging
import threading
from typing import Dict, List
from time import sleep
from datetime import datetime
import textwrap

import chardet

from xpwebapi import CALLBACK_TYPE, DATAREF_DATATYPE, Dataref

import winwing
from winwing.devices import mcdu  # Must import since it contains references to other classes
from winwing.helpers.aircraft import Aircraft
from ..winwing import WinwingDevice
from .device import SPECIAL_CHARACTERS, MCDUDevice, MCDU_DEVICE_MASKS
from .report import MCDUDeviceReport, MCDUSimulatorReport
from .constant import (
    AIRCRAFT_DATAREFS,
    ICAO_DATAREF,    AUTHOR_DATAREF,    MCDU_ANNUNCIATORS,
    MCDU_BRIGHTNESS,
    BRIGHTNESS_AUTO_ADJUST,
    SENSOR_CHECK_FREQUENCY,
    COLORS,
    MCDU_STATUS,
    PAGE_LINES,
    PAGE_CHARS_PER_LINE,    PAGE_BYTES_PER_CHAR,
    PAGE_BYTES_PER_LINE,)

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
# When repetitive warnings, only show first ones:
MAX_WARNING_COUNT = 3

AUTHOR_REPORT = {"report-type": "simulator-value-change", "simulator-value-name": "sim/aircraft/view/acf_author", "action": "change-aircraft"}
ICAO_REPORT = {"report-type": "simulator-value-change", "simulator-value-name": "sim/aircraft/view/acf_ICAO", "action": "change-aircraft"}
ALWAYS_REPORTS = [ICAO_REPORT, AUTHOR_REPORT]


class MCDU(WinwingDevice):
    """Winwing MCDU Coordinator

    Connect to Winwing MCDU and listen for keypresses. Submit corresponding command to X-Plane.
    Connect to X-Plane and monitor MCDU datarefs. Update MCDU appearance accordingly.

    """

    WINWING_PRODUCT_IDS = [47926, 47930, 47934]
    VERSION = "0.11.0"

    def __init__(self, vendor_id: int, product_id: int, **kwargs):
        WinwingDevice.__init__(self, vendor_id=vendor_id, product_id=product_id)
        self._status = MCDU_STATUS.RUNNING
        self._ready = False
        self.status = MCDU_STATUS.NOT_RUNNING
        self.device = MCDUDevice(vendor_id=vendor_id, product_id=product_id)

        # self.api = ws_api(host=kwargs.get("host", "127.0.0.1"), port=kwargs.get("port", "8086"))
        self.api = None  # ws_api(host="192.168.1.140", port="8080")

        self._extension_paths = []
        self.VALID_AIRCRAFTS = Aircraft.list()

        self.aircraft = None
        self.aircraft_config = None
        self._datarefs = {}
        self._loaded_datarefs = set()

        self.display_datarefs = []
        self.mcdu_units = set()

        self.author = ""
        self.icao = ""
        self.variant: str | None = None

        self.new_icao = None
        self.new_author = None
        self.new_acf = {}

        self.device_reports = []
        self._device_reports_by_id = {}
        self.simulator_reports = [MCDUSimulatorReport.new(config=s, device=self) for s in ALWAYS_REPORTS]
        self._simulator_reports_by_id = {s.key: s for s in self.simulator_reports}

        self.display = MCDUDisplay(device=self.device)
        self.brightness = {}
        self.sensors = {"left": 0, "right": 0}

        # Working variables
        self._warned = False
        self._buttons_press_event = [0] * len(self.device_reports)
        self._buttons_release_event = [0] * len(self.device_reports)
        self._last_large_button_mask = 0
        self._sensor_delta = 200
        self._reads = 0
        self.init()

    @property
    def status(self) -> MCDU_STATUS:
        """Should use REST API for some purpose"""
        return self._status

    @property
    def status_str(self) -> str:
        """Should use REST API for some purpose"""
        return f"{MCDU_STATUS(self._status).name}"

    @property
    def aircraft_forced(self) -> bool:
        return self.aircraft_config is not None

    @status.setter
    def status(self, status: MCDU_STATUS):
        if self._status != status:
            self._status = status
            logger.info(f"MCDU status is now {self.status_str}")

    def set_api(self, api):
        self.api = api
        self.api.add_callback(CALLBACK_TYPE.ON_DATAREF_UPDATE, self.on_dataref_update)
        self.api.add_callback(CALLBACK_TYPE.ON_CLOSE, self.on_lost_connection)

    def init(self):
        self.display.test_screen()
        self.device.clear()
        self.display.clear_page()
        self.display.set_background(8)
        sleep(2)
        self.display.message("Welcome", extra=True)

    def reset_buttons(self):
        self._buttons_press_event = [0] * len(self.device_reports)
        self._buttons_release_event = [0] * len(self.device_reports)
        self._last_large_button_mask = 0
        self._ready = True

    def set_aircraft_configuration(self, filename):
        self.aircraft_config = filename

    def set_extension_paths(self, extension_paths: List[str]):
        self._extension_paths = extension_paths
        self.VALID_AIRCRAFTS = Aircraft.list(extension_paths=extension_paths)

    def aircraft_from_configuration_file(self):
        logger.debug("..loading aircraft from configuration file..")
        a = Aircraft.load_from_file(filename=self.aircraft_config)
        if a is not None:
            logger.info(f"using aircraft configuration {self.aircraft_config}, adapter {type(a)}")
            return a
        return None

    def load_aircraft(self):

        def strip_index(path):  # path[5] -> path
            return path.split("[")[0]

        logger.debug("loading aircraft..")
        if not self.aircraft_forced:
            self.aircraft = Aircraft.new(author=self.author, icao=self.icao, extension_paths=self._extension_paths)
        else:
            self.aircraft = self.aircraft_from_configuration_file()
            if self.aircraft is None:
                logger.error(f"cannot load aircraft from configuration file {self.aircraft_config}")
            else:  # transfer data acf -> mcdu
                self.author = self.aircraft.author
                self.icao = self.aircraft.icao
                self.variant = self.aircraft.variant

        self.display.set_aircraft(self.aircraft)

        # Load device and simulator reports
        self.device_reports = [MCDUDeviceReport.new(config=d, simulator=self.api) for d in self.aircraft.device_reports()]
        self._device_reports_by_id = {d.key: d for d in self.device_reports}

        self.simulator_reports = [MCDUSimulatorReport.new(config=s, device=self) for s in self.aircraft.simulator_reports()]
        self._simulator_reports_by_id = {s.key: s for s in self.simulator_reports}
        # Add allways report datarefs
        if ICAO_DATAREF not in self._simulator_reports_by_id:
            self.simulator_reports.append(MCDUSimulatorReport.new(config=ICAO_REPORT, device=self))
        if AUTHOR_DATAREF not in self._simulator_reports_by_id:
            self.simulator_reports.append(MCDUSimulatorReport.new(config=AUTHOR_REPORT, device=self))
        self._simulator_reports_by_id = {s.key: s for s in self.simulator_reports}

        self.mcdu_units = self.aircraft.mcdu_units

        # Collects and registers datarefs in use
        drefs1 = self.aircraft.display_datarefs()
        drefs2 = [d for d in self.aircraft.datarefs() if d not in drefs1]
        drefs_display = set([self.aircraft.set_mcdu_unit(str_in=d, mcdu_unit=self.device.mcdu_unit_id) for d in drefs1])
        drefs_no_display = set([self.aircraft.set_mcdu_unit(str_in=d, mcdu_unit=self.device.mcdu_unit_id) for d in drefs2])
        self.display_datarefs = set([strip_index(d) for d in drefs_display])
        self._loaded_datarefs = drefs_display | drefs_no_display
        self.register_datarefs(paths=self._loaded_datarefs)
        logger.debug(f"registered {len(self._loaded_datarefs)} datarefs for MCDU {self.device.mcdu_unit_id}, {len(self.display_datarefs)} required")
        self.display.set_display_datarefs(dataref_list=self.display_datarefs, mcdu_units=self.mcdu_units)
        logger.debug(f"loaded aircraft {self.icao}")
        # To do? collects and registers command active reports?

    def unload_aircraft(self):
        old_icao = self.icao
        logger.debug(f"unloading aircraft {old_icao}..")
        self.unload_datarefs()
        self.device_reports = []
        self._device_reports_by_id = {}
        self.simulator_reports = [MCDUSimulatorReport.new(config=s, device=self) for s in ALWAYS_REPORTS]
        self._simulator_reports_by_id = {s.key: s for s in self.simulator_reports}
        self.mcdu_units = []
        self.aircraft = None
        logger.debug(f"..unloaded aircraft {self.icao}")

    def unload_datarefs(self):
        self.unregister_datarefs(paths=list(self._loaded_datarefs))

    def get_dataref_value(self, path: str, encoding: str = "ascii") -> int | float | str | None:
        """Returns the value of a single dataref"""
        d = self._datarefs.get(path)
        value = d.value if d is not None else None
        if type(value) is bytes and d.value_type == DATAREF_DATATYPE.DATA.value:
            try:
                value = value.decode(encoding=encoding).replace("\u0000", "")
            except:
                logger.warning(f"could not decode value {value} with encoding {encoding}", exc_info=True)
        return value

    def register_datarefs(self, paths: List[str]):
        self._datarefs = self._datarefs | {p: Dataref(api=self.api, path=p) for p in paths if p not in self._datarefs}
        self.api.monitor_datarefs(datarefs=self._datarefs, reason=f"Winwing MCDU register {self.icao}")

    def unregister_datarefs(self, paths: List[str]):
        # Ignore supplied list, unregister all registered datarefs
        self.api.unmonitor_datarefs(datarefs=self._datarefs, reason=f"Winwing MCDU unregister {self.icao}")

    def unregister_all_datarefs(self):
        self.api.unmonitor_datarefs(datarefs=self._datarefs, reason="Winwing MCDU terminates")

    def run(self):
        logger.debug("starting..")
        self.device.set_callback(self.reader_callback)
        self.device.start()
        self.display.message("waiting for X-Plane...")
        self.api.connect()
        self.wait_for_resources()
        logger.debug("..started")

    def terminate(self):
        logger.debug("terminating..")
        # stop receiving actions from devices
        self.device.set_callback(None)
        # ask to stop sending dataref updates
        self.unregister_all_datarefs()
        # disconnect api
        self.api.disconnect()
        # stop display update loop
        self.display.stop_update()
        # clear screen
        self.device.clear()
        # turn off all annunciator
        for a in MCDU_ANNUNCIATORS:
            self.set_annunciator(annunciator=a, on=False)
        self.device.terminate()
        logger.debug("..terminated")

    def reader_callback(self, data_in):
        def xor_bitmask(a, b, bitmask):
            return (a & bitmask) != (b & bitmask)

        if not self._ready:
            # Some messages are sent upon initialisation, we ignore them
            return
        large_button_mask = 0
        for i in range(12):
            large_button_mask |= data_in[i + 1] << (8 * i)

        for i in range(len(self.device_reports)):
            mask = 0x01 << i
            if xor_bitmask(large_button_mask, self._last_large_button_mask, mask):
                self.do_keypress(i, pressed=(large_button_mask & mask))
        self._last_large_button_mask = large_button_mask

        if self._reads % SENSOR_CHECK_FREQUENCY == 0:
            self.do_sensors(data_in)
        self._reads = self._reads + 1

    def on_lost_connection(self):
        self.display.message("waiting for X-Plane...")
        self.api.disconnect()  # cleanup existing
        self.api.connect()  # restarts from no connection
        self.wait_for_resources()

    def wait_for_xplane(self):
        """Wait for X-Plane API reachability"""
        self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.FAIL, on=False)
        self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.RDY, on=False)
        self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.STATUS, on=False)
        warning_count = 0
        if not self.api.connected:
            self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.FAIL, on=True)
            while not self.api.connected:
                if warning_count <= MAX_WARNING_COUNT:
                    last_warning = " (last warning)" if warning_count == MAX_WARNING_COUNT else ""
                    logger.warning(f"waiting for X-Plane{last_warning}")
                warning_count = warning_count + 1
                sleep(2)
            logger.info("connected to X-Plane")
        self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.FAIL, on=False)
        self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.STATUS, on=True)
        self.status = MCDU_STATUS.CONNECTED

    def wait_for_aircraft(self):
        """Wait for value of both
        - AUTHOR_DATAREF = "sim/aircraft/view/acf_author"
        - ICAO_DATAREF = "sim/aircraft/view/acf_ICAO"
        """
        if self.aircraft_forced:
            logger.info("aircraft from supplied configuration file")
            self.status = MCDU_STATUS.AIRCRAFT_DETECTED
            return
        self.register_datarefs(paths=AIRCRAFT_DATAREFS)
        if not self._ready:
            self.display.message("waiting for aircraft...")
        icao = self.get_dataref_value(path=ICAO_DATAREF)
        author = self.get_dataref_value(path=AUTHOR_DATAREF)
        key = Aircraft.key(author=author, icao=icao)
        warning_count = 0
        if key not in self.VALID_AIRCRAFTS:
            while key not in self.VALID_AIRCRAFTS:
                if warning_count <= MAX_WARNING_COUNT:
                    last_warning = " (last warning)" if warning_count == MAX_WARNING_COUNT else ""
                    logger.warning(f"waiting for valid aircraft (current {key} not in list {self.VALID_AIRCRAFTS.keys()}{last_warning}")
                warning_count = warning_count + 1
                sleep(2)
                icao = self.get_dataref_value(ICAO_DATAREF)
                author = self.get_dataref_value(AUTHOR_DATAREF)
                key = Aircraft.key(author=author, icao=icao)
        self.icao = icao
        self.author = author
        logger.info(f"{self.author} {self.icao} detected")
        self.status = MCDU_STATUS.AIRCRAFT_DETECTED
        # no change to status lights, we still need the data

    def wait_for_metadata(self):
        warning_count = 0
        if not self.api.has_data:
            while not self.api.has_data:
                self.api.reload_caches(force=True)
                if not self.api.has_data:
                    if warning_count <= MAX_WARNING_COUNT:
                        last_warning = " (last warning)" if warning_count == MAX_WARNING_COUNT else ""
                        logger.warning(f"waiting for api metadata{last_warning}")
                    warning_count = warning_count + 1
                    sleep(2)
        logger.info("api metadata cached")

    def wait_for_data(self):
        """Wait necessary data for display.

        Registers the aircraft datarefs and wait for all "required" datarefs to have a value.
        """

        def data_count():
            drefs = {d.path: d.value for d in self._datarefs.values()}
            reqs = filter(lambda k: k in self.display_datarefs and drefs.get(k) is not None, drefs.keys())
            return len(list(reqs))

        ## Wait for API dataref meta data in cache?
        self.wait_for_metadata()
        # logger.debug("registering datarefs..")
        # self.load_datarefs()
        # logger.debug("..registered")
        logger.debug("loading aircraft data..")
        self.load_aircraft()
        logger.debug("..aircraft loaded")
        if not self.aircraft.loaded:
            self.display.message("no aircraft")
            self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.FAIL, on=True)
            return
        # self.status = MCDU_STATUS.CONNECTED
        # self.aircraft.wait_for_aircraft_variant(api=self)
        # self.status = MCDU_STATUS.AIRCRAFT_DETECTED
        if not self._ready:
            self.display.message("waiting for data...")
        self.status = MCDU_STATUS.WAITING_FOR_DATA
        self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.STATUS, on=False)
        self.set_unit_warning()
        sleep(2)  # give a chance for data to arrive, 2.0 secs sufficient on medium computer
        expected = len(self.display_datarefs)
        cnt = data_count()
        warning_count = 0
        if cnt != expected:
            self.status = MCDU_STATUS.WAITING_FOR_DATA
            while cnt != expected:
                if warning_count <= MAX_WARNING_COUNT or warning_count % 30 == 0:
                    last_warning = " (last warning)" if warning_count == MAX_WARNING_COUNT else ""
                    logger.warning(f"waiting for MCDU data ({cnt}/{expected}){last_warning}")
                warning_count = warning_count + 1
                sleep(2)
                cnt = data_count()
        logger.info(f"MCDU {expected} data received")
        self.set_unit_warning(on=False)
        self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.RDY, on=True)
        # turn off RDY two seconds later, RDY is used in CPLDC messaging
        timer = threading.Timer(1.0, self.device.set_led, args=(MCDU_ANNUNCIATORS.RDY, False))
        timer.start()

    def wait_for_resources(self):
        self.wait_for_xplane()
        self.wait_for_aircraft()
        self.wait_for_data()
        self.reset_buttons()

        self.status = MCDU_STATUS.RUNNING
        self._warned = False

    def on_dataref_update(self, dataref: str, value):
        """Receive dataref updates and need to locate associated SimulatorReport

        [description]

        Args:
            dataref (str): [description]
            value ([type]): [description]
        """

        d = self._datarefs.get(dataref)
        if d is None:
            logger.warning(f"dataref {dataref} not found in registed datarefs")
            return
        d.value = value

        if type(value) is bytes:  # this is a string, try to decode it
            if self.aircraft is not None:
                value = self.aircraft.encode_bytes(dataref=d, value=value)
            else:
                enc = chardet.detect(value)
                if enc["confidence"] > 0.2:
                    value = value.decode(enc["encoding"]).replace("\u0000", "")
                else:
                    logger.warning(f"cannot decode bytes for {dataref} ({enc})")

        report = self._simulator_reports_by_id.get(dataref)
        if report is None:
            logger.warning(f"no report for {dataref} ({value})")
            return

        report.activate(mcdu=self, value=value)
        return

        # MCDU text datarefs
        if self.aircraft is None:
            logger.warning("no aircraft")
            return

    def do_keypress(self, key_id: int, pressed: bool):
        report = self._device_reports_by_id.get(key_id)
        if report is None:
            logger.warning(f"device report for key {key_id} not found")
            return
        if pressed:  # todo: move this cond inside report
            report.activate(mcdu=self, pressed=pressed)

    def change_mcdu_unit(self) -> int:
        # To do:
        # 1. Unregister current unit datarefs
        self.set_unit_warning()
        self.unload_datarefs()
        # 2. Change unit id
        self.set_unit_warning(on=False)
        self.device.set_unit(MCDU_DEVICE_MASKS.FO if self.device.mcdu_unit & MCDU_DEVICE_MASKS.CAP else MCDU_DEVICE_MASKS.CAP)
        # 3. Register new unit datarefs and wait for data
        self.wait_for_data()
        logger.info(f"MCDU unit {self.device.mcdu_unit_id}")
        self.display._updated.set()
        return self.device.mcdu_unit_id

    def change_aircraft(self, new_author: str, new_icao: str) -> str:
        # To do:
        valid_icao_aircrafts = [a[: a.index("::")] for a in self.VALID_AIRCRAFTS]
        if new_icao not in valid_icao_aircrafts:
            logger.warning(f"{new_icao} not in list {','.join(valid_icao_aircrafts)}")
            logger.warning(f"aircraft discrepency MCDU aircraft {self.icao} vs X-Plane aircraft {new_icao}")
            return self.icao

        if self.aircraft_forced:
            logger.warning(f"MCDU uses a user-supplied aircraft configuration for {self.icao} (file {self.aircraft_config})")
            logger.warning(f"aircraft discrepency MCDU aircraft {self.icao} vs X-Plane aircraft {new_icao}")
            logger.warning(f"stop and restart winwing-cli without custom aircraft configuration to handle current aircraft {new_icao}")
            return self.icao

        if new_icao == self.icao and new_author == self.author:
            logger.debug("same aicraft, no need to change")
            return self.icao

        # 1. Unregister current unit datarefs
        self.set_annunciator(annunciator=MCDU_ANNUNCIATORS.STATUS, on=True)  # will be set off in wait_for_data

        # 2. Change aircraft
        self.unload_aircraft()
        self.author = new_author
        self.icao = new_icao

        # 3. Load new aircraft datarefs and wait for data
        self.wait_for_aircraft()
        self.wait_for_data()
        logger.info(f"aircraft is now {self.icao}")
        return self.icao

    def do_sensors(self, data_in):
        w = False
        v = 256 * int(data_in[18]) + int(data_in[17])
        dl = v - self.sensors["left"]
        if abs(dl) > self._sensor_delta:
            w = True
            self.sensors["left"] = v
        v = 256 * int(data_in[20]) + int(data_in[19])
        dr = v - self.sensors["right"]
        if abs(dr) > self._sensor_delta:
            w = True
            self.sensors["right"] = v
        if w:
            logger.debug(f"sensors: left {self.sensors['left']} ({dl}), right {self.sensors['right']} ({dr})")

        if not BRIGHTNESS_AUTO_ADJUST:
            return
        # Auto adjust back light brightness
        GLOBAL_BRIGHTNESS = "_global"
        avg = int((self.sensors["left"] + self.sensors["right"]) / 2)
        maxlevel = 100000
        for r in BRIGHTNESS_AUTO_ADJUST:
            if maxlevel > avg >= r[0]:
                if self.brightness.get(GLOBAL_BRIGHTNESS, "") != r[4]:
                    self.device.set_brightness(backlight=MCDU_BRIGHTNESS.BACKLIGHT, brightness=r[1])
                    self.device.set_brightness(backlight=MCDU_BRIGHTNESS.SCREEN_BACKLIGHT, brightness=r[2])
                    self.device.set_brightness(backlight=MCDU_BRIGHTNESS.LEDS_BRIGHTNESS, brightness=r[3])
                    logger.info(f"brightness auto adjust to {r[4]}")
                    logger.debug(f"brightness auto adjust: {r[4]} ({avg}): keyboard: {r[1]}, LCD: {r[2]}, LEDS: {r[3]}")
                    self.brightness[GLOBAL_BRIGHTNESS] = r[4]
                    break
            maxlevel = r[0]

    def set_annunciator(self, annunciator: MCDU_ANNUNCIATORS, on: bool = True):
        self.device.set_led(led=annunciator, on=on)

    def set_unit_warning(self, on: bool = True):
        self.device.set_unit_led(on=on)


# ##################
#
# MCDU Display Controller
#
class MCDUTerminal:
    """Character-based display of MCDU content.

    Updated on the console each time the display is refreshed.
    Mainly used for development purpose.

    """

    def display(self, page: list):
        """Create display mock-up on terminal for page returns string.

        Args:
            page (list): Page content

        Returns:
            str: characters ready to display, include newlines.
        """
        output = io.StringIO()
        print("\n", file=output)
        print("|------ MCDU SCREEN -----|", file=output)
        for i in range(PAGE_LINES):
            print("|", end="", file=output)
            for j in range(PAGE_CHARS_PER_LINE):
                val = page[i][j * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1]
                if val == "#":
                    # val = "▯"
                    val = "☐"
                if val == "`":
                    val = "°"
                # if val == ">":
                #     val = "🠊"
                # if val == "<":
                #     val = "🠈"
                print(val, end="", file=output)
            print("|", file=output)
        print("|------------------------|", file=output)
        print("", file=output)
        contents = output.getvalue()
        output.close()
        return contents


class MCDUColorTerminal:
    """Character-based display of MCDU content.

    Updated on the console each time the display is refreshed.
    Mainly used for development purpose.

    """

    def display_page(self, page: list):
        """Create display mock-up on terminal for page returns string.

        Args:
            page (list): Page content

        Returns:
            str: characters ready to display, include newlines.
        """
        TERMINAL_COLOR_CODES = {c.key: c.term for c in COLORS}
        print("\n")
        for i in range(PAGE_LINES):
            for j in range(PAGE_CHARS_PER_LINE):
                curr = ""
                c = page[i][j * PAGE_BYTES_PER_CHAR : (j + 1) * PAGE_BYTES_PER_CHAR]
                # c[1] is bool small_font, ignored for terminal
                if c[0] == "s":  # "special" characters (rev. eng.)
                    if c[2] == chr(35):
                        c[2] = "☐"
                    elif c[2] == chr(60):
                        c[2] = "←"
                    elif c[2] == chr(62):
                        c[2] = "→"
                    elif c[2] == chr(91):
                        c[2] = "["
                    elif c[2] == chr(93):
                        c[2] = "]"
                if c[2] == "`":
                    c[2] = "°"
                if curr != c[0]:
                    curr = c[0]
                    print(TERMINAL_COLOR_CODES.get(c[0], "\033[38;5;231m"), end="")  # default to white
                print(c[2], end="")
            print("")
        print("\033[0m")  # reset
        print("\n")


class MCDUDisplay:
    """MCDU display content.

    Updated when datarefs govering content are updated.
    """

    def __init__(self, device):
        self.device = device
        self.aircraft = None
        self.terminal = None  # MCDUColorTerminal()

        self.page = [[" " for _ in range(PAGE_BYTES_PER_LINE)] for _ in range(PAGE_LINES)]
        self.display_datarefs = set()
        self.mcdu_units = set()
        self.datarefs = {}

        self._all_ok = False
        self._last_display = datetime.now()
        self._updated = threading.Event()
        self.update_event = threading.Event()
        self.update_thread = threading.Thread(target=self.update, name="MCDU Screen Updater")
        self.update_thread.start()

    def set_aircraft(self, aircraft: Aircraft):
        self.aircraft = aircraft

    def set_display_datarefs(self, dataref_list: set, mcdu_units: set):
        self.display_datarefs = dataref_list
        self.mcdu_units = mcdu_units

    def clear_page(self):
        self.page = []
        for i in range(PAGE_LINES):
            line = []
            for j in range(PAGE_CHARS_PER_LINE):
                line.extend([COLORS.DEFAULT, False, " "])
            self.page.append(line)

    def clear_lines(self):
        if self.aircraft is not None:
            self.aircraft.clear_lines()
        self._all_ok = False

    def message(self, message, extra: bool = False):
        def center_line(line: int, text: str, color: COLORS, font_small: bool = False):
            text = text[:PAGE_CHARS_PER_LINE]
            startpos = int((PAGE_CHARS_PER_LINE - len(text)) / 2)
            self.write_line_to_page(line, startpos, text, color, font_small)

        self.device.clear()
        self.clear_page()

        # Heading
        title = "WINWING for X-Plane"
        idx = title.index("G") + int((PAGE_CHARS_PER_LINE - len(title)) / 2)
        center_line(0, title, COLORS.DEFAULT)
        self.page[0][idx * PAGE_BYTES_PER_CHAR] = COLORS.RED

        # Message
        center_line(8, message, COLORS.AMBER)

        # Extra (version information)
        if extra:
            center_line(1, f"VERSION {winwing.version}", COLORS.CYAN, True)
            self.write_line_to_page(3, 0, " MCDU", COLORS.WHITE, True)
            self.write_line_to_page(4, 0, f"{chr(SPECIAL_CHARACTERS.ARROW_LEFT)}{MCDU.VERSION}", COLORS.CYAN, False)
            center_line(12, "github.com/devleaks", COLORS.DEFAULT, True)
            title = "/pywinwing"
            center_line(13, title, COLORS.DEFAULT, True)
            idx = title.index("g") + int((PAGE_CHARS_PER_LINE - len(title)) / 2)
            self.page[13][idx * PAGE_BYTES_PER_CHAR] = COLORS.RED
        self.device.display_page(page=self.page)
        if extra:
            sleep(1)

    def set_background(self, code: int = 8):
        if code < 0 or code > 8:
            logger.warning(f"invalid background color code {code}")
            return
        bi = 0x32
#fmt off
        data = [0xF0, 0x00, 0x0A, 0x12, bi, 0xBB, 0x00, 0x00, 0x04, 0x01, 0x00, 0x00, 0xD4, 0xAC, 0x09, 0x00]
        xtra = [
            0x00,0x01,0x00,0x00,0x00,(0x0C + code),0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00
        ]
#fmt on
        self.device.write(bytes(data + xtra))

    def test_screen(self):
        self.device.clear()
        self.clear_page()
        self.set_background(8)
        sleep(1)
        # for i in range(9):
        #     self.set_background(i)
        #     sleep(1)
        prnt = "".join([chr(c) for c in range(33, 127)])
        lines = textwrap.wrap(prnt, 23)
        lines.append("".join([chr(c.value) for c in SPECIAL_CHARACTERS]))
        i = 0
        for c in COLORS:
            if i < 14:
                self.write_line_to_page(i, 0, lines[i % len(lines)], c, False)
                i = i + 1
        for c in COLORS:
            if i < 14:
                self.write_line_to_page(i, 0, lines[i % len(lines)], c, False)
                i = i + 1
        self.device.display_page(page=self.page)
        sleep(10)

    def write_line_to_page(self, line, pos, text: str, color: COLORS, font_small: bool = False):
        if not (0 <= line <= PAGE_LINES):
            logger.warning(f"line number out of range {line}, {text}")
            return
        if pos < 0 or pos + len(text) >= PAGE_CHARS_PER_LINE:
            logger.warning(f"text line overflow {pos}, {len(text)}, {text}")
            return
        if len(text) > PAGE_CHARS_PER_LINE:
            logger.warning(f"text too long for line {len(text)}, {text}")
            return
        # data_low, data_high = self._data_from_col_font(color, font_small)
        pos = pos * PAGE_BYTES_PER_CHAR
        for c in range(len(text)):
            self.page[line][pos + c * PAGE_BYTES_PER_CHAR] = color
            self.page[line][pos + c * PAGE_BYTES_PER_CHAR + 1] = font_small
            self.page[line][pos + c * PAGE_BYTES_PER_CHAR + PAGE_BYTES_PER_CHAR - 1] = text[c]

    def display(self, page: list | None = None):
        self.device.display_page(page=self.page if page is None else page)

    def all_datarefs_available_count(self) -> bool:
        avail_drefs = filter(lambda x: x in self.display_datarefs, self.datarefs)
        return len(list(avail_drefs))

    def all_datarefs_available(self) -> bool:
        return self.all_datarefs_available_count() == len(self.display_datarefs)

    def variable_changed(self, dataref: str, value):
        self.datarefs[dataref] = value

        if self.aircraft is None:
            logger.warning("no aircraft")
            return

        self.aircraft.variable_changed(dataref=dataref, value=value)

        # Processing completed
        # is this dataref related to the unit we are currently displaying?
        if self.aircraft.get_mcdu_unit(dataref) != self.device.mcdu_unit_id:
            # logger.debug(f"{dataref} does not belong to unit on display ({mcdu_unit})")
            return

        if not self.all_datarefs_available():
            # if (len(self.display_datarefs) - self.all_datarefs_available_count()) < 4:
            #     print("still missing", set(self.display_datarefs) - set(self.datarefs.keys()))
            return

        if not self._all_ok:
            logger.debug(f"all {len(self.display_datarefs)} required dataref available")
            self._all_ok = True

        self._updated.set()

    def update(self):
        """Queueing mechanism to prevent concurrent updates"""
        logger.debug("display updater started")
        while not self.update_event.is_set():
            if self._updated.wait(1):
                self._updated.clear()  # we clear first since an update may come while we refresh the display
                self.show_page()  # _laminar
        logger.debug("display updater terminated")

    def stop_update(self):
        self.update_event.set()

    def show_page(self):
        self.page = self.aircraft.show_page(mcdu_unit=self.device.mcdu_unit_id)

        # display mcdu on winwing
        self.device.display_page(page=self.page)
        if self.terminal is not None:
            self.terminal.display_page(page=self.page)


# ##################
#
# M A I N
#
# if __name__ == "__main__":
#     FORMAT = "[%(asctime)s] %(levelname)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
#     logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="%H:%M:%S")

#     api = XP_NET_API()
#     mcdu = MCDU(api=api)
#     try:
#         mcdu.run()
#     except (KeyboardInterrupt, EOFError):
#         if mcdu is not None:
#             mcdu.terminate()
