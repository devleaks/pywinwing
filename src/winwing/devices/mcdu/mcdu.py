from __future__ import annotations
import io
import logging
import threading
import re
from typing import Dict, List
from time import sleep
from datetime import datetime

from xpwebapi import CALLBACK_TYPE, Dataref, Command

from ..winwing import WinwingDevice
from .aircraft import MCDUAircraft, MCDU_DISPLAY_DATA

from .device import MCDUDevice, MCDU_DEVICE_MASKS
from .constant import (
    ButtonType,
    DrefType,
    Button,
    AIRCRAFT_DATAREFS,
    ICAO_DATAREF,
    VENDOR_DATAREF,
    VALID_ICAO_AIRCRAFTS,
    MCDU_ANNUNCIATORS,
    MCDU_BRIGHTNESS,
    MCDU_TERM_COLORS,
    MCDU_COLOR,
    MCDU_STATUS,
    PAGE_LINES,
    PAGE_CHARS_PER_LINE,
    PAGE_BYTES_PER_CHAR,
    PAGE_BYTES_PER_LINE,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

version = "0.6.1"


class MCDU(WinwingDevice):
    """Winwing MCDU Coordinator

    Connect to Winwing MCDU and listen for keypresses. Submit corresponding command to X-Plane.
    Connect to X-Plane and monitor MCDU datarefs. Update MCDU appearance accordingly.

    """

    def __init__(self, vendor_id: int, product_id: int, **kwargs):
        WinwingDevice.__init__(self, vendor_id=vendor_id, product_id=product_id)
        self._status = MCDU_STATUS.RUNNING
        self._ready = False
        self.status = MCDU_STATUS.NOT_RUNNING
        self.device = MCDUDevice(vendor_id=vendor_id, product_id=product_id)

        # self.api = ws_api(host=kwargs.get("host", "127.0.0.1"), port=kwargs.get("port", "8086"))
        self.api = None  # ws_api(host="192.168.1.140", port="8080")
        self.aircraft = None
        self._datarefs = {}
        self._loaded_datarefs = set()

        self.required_datarefs = []
        self.mcdu_units = set()

        self.vendor = ""
        self.icao = ""
        self.variant: str | None = None

        self.buttons = []
        self._buttons_by_id = {}

        self.display = MCDUDisplay(device=self.device)
        self.brightness = {}

        # Working variables
        self._warned = False
        self._buttons_press_event = [0] * len(self.buttons)
        self._buttons_release_event = [0] * len(self.buttons)
        self._last_large_button_mask = 0
        self._left_sensor = 0  # sensors values runs from 0..255
        self._right_sensor = 0
        self._sensor_delta = 256
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

    @status.setter
    def status(self, status: MCDU_STATUS):
        if self._status != status:
            self._status = status
            logger.info(f"MCDU status is now {self.status_str}")

    def set_api(self, api):
        self.api = api
        self.api.add_callback(CALLBACK_TYPE.ON_DATAREF_UPDATE, self.on_dataref_update)

    def init(self):
        self.display.startup_screen()

    def reset_buttons(self):
        self._buttons_press_event = [0] * len(self.buttons)
        self._buttons_release_event = [0] * len(self.buttons)
        self._last_large_button_mask = 0
        self._ready = True

    def load_aircraft(self):
        DREF_TYPE = {"command": DrefType.CMD, "data": DrefType.DATA, "none": DrefType.NONE}
        BUTTON_TYPE = {"none": ButtonType.NONE, "press": ButtonType.TOGGLE, "switch": ButtonType.SWITCH}
        BRIGHTNESS = {
            "screen_backlight": MCDU_BRIGHTNESS.SCREEN_BACKLIGHT,
            "backlight": MCDU_BRIGHTNESS.BACKLIGHT,
        }

        def mk_button(b: list) -> Button:
            b[3] = DREF_TYPE[b[3]]
            b[4] = BUTTON_TYPE[b[4]]
            if b[5] is not None and b[5].lower() != "none":
                b[5] = BRIGHTNESS[b[5]]
            return Button(*b)

        def strip_index(path):  # path[5] -> path
            return path.split("[")[0]

        self.aircraft = MCDUAircraft(vendor=self.vendor, icao=self.icao, variant=self.variant)

        # Install buttons
        self.buttons = [mk_button(b) for b in self.aircraft.mapped_keys()]
        self._buttons_by_id = {b.id: b for b in self.buttons}

        self.mcdu_units = self.aircraft.mcdu_units

        drefs1 = self.aircraft.required_datarefs()
        drefs2 = [d for d in self.aircraft.datarefs() if d not in drefs1]
        drefs_display = set([self.set_mcdu_unit(d) for d in drefs1])
        drefs_no_display = set([self.set_mcdu_unit(d) for d in drefs2])
        self.required_datarefs = set([strip_index(d) for d in drefs_display])
        self._loaded_datarefs = drefs_display | drefs_no_display
        self.register_datarefs(paths=self._loaded_datarefs)
        logger.debug(f"registered {len(self._loaded_datarefs)} datarefs for {self.set_mcdu_unit('MCDU1')}, {len(self.required_datarefs)} required")
        self.display.set_display_datarefs(dataref_list=self.required_datarefs, mcdu_units=self.mcdu_units)

    def unload_datarefs(self):
        self.unregister_datarefs(paths=list(self._loaded_datarefs))

    def get_dataref_value(self, path: str) -> int | float | str | None:
        """Returns the value of a single dataref"""
        d = self._datarefs.get(path)
        return d.value if d is not None else None

    def get_all_dataref_values(self) -> Dict[str, int | float | str | None]:
        """Returns all registered datarefs and their values"""
        return {d.path: d.value for d in self._datarefs.values()}

    def set_dataref_value(self, path: str, value: int | float | str):
        """Set the value of a dataref"""
        d = self._datarefs.get(path)
        if d is None:
            return
        d.value = value
        d.write()

    def execute_command(self, path: str):
        """Execute a command"""
        # inefficient if not using cache since cause cmd_id lookup on each invoque
        # (default is to use cache)
        c = Command(api=self.api, path=path)
        c.execute()

    def register_datarefs(self, paths: List[str]):
        self._datarefs = self._datarefs | {p: Dataref(api=self.api, path=p) for p in paths if p not in self._datarefs}
        self.api.monitor_datarefs(datarefs=self._datarefs, reason="Winwing MCDU")

    def unregister_datarefs(self, paths: List[str]):
        # Ignore supplied list, unregister all registered datarefs
        self.api.unmonitor_datarefs(datarefs=self._datarefs, reason="Winwing MCDU")

    def unregister_all_datarefs(self):
        self.api.unregister_bulk_dataref_value_event(datarefs=self._datarefs, reason="Winwing MCDU")

    def run(self):
        logger.debug("starting..")
        self.device.set_callback(self.reader_callback)
        self.device.start()
        self.api.connect()
        self.wait_for_resources()
        logger.debug("..started")

    def terminate(self):
        logger.debug("terminating..")
        self.device.set_callback(None)
        self.api.disconnect()
        self.display.stop_update()
        self.device.stop()
        logger.debug("..terminated")

    def set_mcdu_unit(self, str_in: str):
        if self.device.mcdu_unit & MCDU_DEVICE_MASKS.FO:
            return re.sub(r"MCDU[123]", "MCDU2", str_in)
        elif self.device.mcdu_unit & MCDU_DEVICE_MASKS.OBS:
            return re.sub(r"MCDU[123]", "MCDU3", str_in)
        return str_in if "MCDU1" in str_in else re.sub(r"MCDU[123]", "MCDU1", str_in)

    def reader_callback(self, data_in):
        def xor_bitmask(a, b, bitmask):
            return (a & bitmask) != (b & bitmask)

        if not self._ready:
            # Some messages are sent upon initialisation, we ignore them
            return
        large_button_mask = 0
        for i in range(12):
            large_button_mask |= data_in[i + 1] << (8 * i)
        # if large_button_mask != 0:
        #     print(f"{large_button_mask:b}", hex(large_button_mask))  # TEST2: you should see a difference when pressing buttons
        for i in range(len(self.buttons)):
            mask = 0x01 << i
            if xor_bitmask(large_button_mask, self._last_large_button_mask, mask):
                # print(f"buttons: {format(large_button_mask, "#04x"):^14}")
                if large_button_mask & mask:
                    self.do_key_press(i)
                else:
                    self.do_key_release(i)
        self._last_large_button_mask = large_button_mask
        if self._reads % 20 == 0:
            self.do_sensors(data_in)
        self._reads = self._reads + 1

    def wait_for_xplane(self):
        self.device.set_led(led=MCDU_ANNUNCIATORS.FAIL, on=False)
        self.device.set_led(led=MCDU_ANNUNCIATORS.RDY, on=False)
        self.device.set_led(led=MCDU_ANNUNCIATORS.STATUS, on=False)
        if not self.api.connected:
            self.device.set_led(led=MCDU_ANNUNCIATORS.FAIL, on=True)
            while not self.api.connected:
                logger.warning("waiting for X-Plane")
                sleep(2)
            logger.info("connected to X-Plane")
        self.device.set_led(led=MCDU_ANNUNCIATORS.FAIL, on=False)
        self.device.set_led(led=MCDU_ANNUNCIATORS.STATUS, on=True)
        self.status = MCDU_STATUS.CONNECTED

    def wait_for_toliss_airbus(self):
        # should check sim/aircraft/view/acf_author == GlidingKiwi
        self.register_datarefs(paths=AIRCRAFT_DATAREFS)
        icao = self.get_dataref_value(ICAO_DATAREF)
        vendor = self.get_dataref_value(VENDOR_DATAREF)
        if icao == "" or icao not in VALID_ICAO_AIRCRAFTS:
            while icao == "" or icao not in VALID_ICAO_AIRCRAFTS:
                logger.warning(f"waiting for valid aircraft (current {icao} not in list {VALID_ICAO_AIRCRAFTS})")
                sleep(2)
                icao = self.get_dataref_value(ICAO_DATAREF)
                vendor = self.get_dataref_value(VENDOR_DATAREF)
            while vendor == "":
                logger.warning("waiting for vendor")
                sleep(2)
                vendor = self.get_dataref_value(VENDOR_DATAREF)
        self.icao = icao
        self.vendor = vendor
        logger.info(f"{self.vendor} {self.icao} detected")
        self.status = MCDU_STATUS.AIRCRAFT_DETECTED
        # no change to status lights, we still need the data

    def wait_for_data(self):
        def data_count():
            drefs = self.get_all_dataref_values()
            reqs = filter(lambda k: k in self.required_datarefs and drefs.get(k) is not None, drefs.keys())
            return len(list(reqs))

        # logger.debug("registering datarefs..")
        # self.load_datarefs()
        # logger.debug("..registered")
        logger.debug("loading aircraft data..")
        self.load_aircraft()
        logger.debug("..aircraft loaded")
        if not self._ready:
            self.display.waiting_for_data()
        self.status = MCDU_STATUS.WAITING_FOR_DATA
        self.device.set_led(led=MCDU_ANNUNCIATORS.STATUS, on=False)
        self.device.set_unit_led()
        sleep(2)  # give a chance for data to arrive, 2.0 secs sufficient on medium computer
        expected = len(self.required_datarefs)
        cnt = data_count()
        if cnt != expected:
            self.status = MCDU_STATUS.WAITING_FOR_DATA
            while cnt != expected:
                logger.warning(f"waiting for MCDU data ({cnt}/{expected})")
                sleep(2)
                cnt = data_count()
        logger.info(f"MCDU {expected} data received")
        self.device.set_unit_led(on=False)
        self.device.set_led(led=MCDU_ANNUNCIATORS.RDY, on=True)
        # turn off RDY two seconds later, RDY is used in CPLDC messaging
        timer = threading.Timer(2.0, self.device.set_led, args=(MCDU_ANNUNCIATORS.RDY, False))
        timer.start()

    def wait_for_resources(self):
        self.wait_for_xplane()
        self.wait_for_toliss_airbus()
        self.wait_for_data()
        self.reset_buttons()

        self.status = MCDU_STATUS.RUNNING
        self._warned = False

    def on_dataref_update(self, dataref: str, value):
        # Save value in dataref
        d = self._datarefs.get(dataref)
        if d is None:
            logger.warning(f"dataref {dataref} not found in registed datarefs")
            return
        d.value = value

        # Special datarefs for brightness control
        if dataref == ICAO_DATAREF:
            if self.aircraft is not None:
                self.change_aircraft(new_icao=value)
            # else, aircraft not loaded yet, will be loaded by wait_for_resources()
        if "Brightness" in dataref or "/anim" in dataref:
            if "DUBrightness" in dataref and value <= 1:
                # brightness is in 0..1, we need 0..255
                value = int(value * 255)
            if dataref not in self.brightness:
                self.brightness[dataref] = value
            elif value != self.brightness[dataref]:
                self.brightness[dataref] = value
                self.set_brightness(dataref, value)
                logger.debug(f"set brightness: {dataref}={value}")
            if "PanelBrightness" in dataref and value <= 1:
                # brightness is in 0..1, we need 0..255
                value = int(value * 255)
            if dataref not in self.brightness:
                self.brightness[dataref] = value
            elif value != self.brightness[dataref]:
                self.brightness[dataref] = value
                self.set_brightness(dataref, value)
                logger.debug(f"set brightness: {dataref}={value}")
        # MCDU text datarefs
        if not MCDUAircraft.is_display_dataref(dataref):
            logger.debug(f"not a display dataref {dataref}")
            return
        self.display.variable_changed(dataref=dataref, value=value)

    def do_key_press(self, key_id: int):
        b = self._buttons_by_id.get(key_id)
        if b is None:
            logger.warning(f"button id {key_id} not found")
            return
        unit_dataref = self.set_mcdu_unit(b.dataref)
        logger.debug(f"button {b.label} pressed ({unit_dataref})")
        if b.type == ButtonType.TOGGLE:
            if b.label == "MENU2":  # special treatment to change MCDU unit
                new_unit = self.change_mcdu_unit()
                logger.debug(f"set mcdu unit {new_unit}")
            elif b.dreftype == DrefType.CMD:
                self.execute_command(unit_dataref)
                logger.debug(f"sent command {unit_dataref}")
            elif b.dreftype == DrefType.DATA:
                val = self.api.get_dataref_value(unit_dataref)
                if val is None:
                    logger.debug(f"button toggle type: no value for {unit_dataref}")
                    return
                self.api.set_dataref_value(unit_dataref, not bool(val))
                logger.debug(f"set dataref {unit_dataref} from {bool(val)} to {not bool(val)}")
        elif b.type == ButtonType.SWITCH:
            if b.dreftype == DrefType.DATA:
                self.api.set_dataref_value(unit_dataref, 1)
                logger.debug(f"set dataref {unit_dataref} to 1")
            elif b.dreftype == DrefType.CMD:
                self.execute_command(unit_dataref)
                logger.debug(f"sent command {unit_dataref}")
        else:
            logger.warning(f"unhandled button type {b.type} for {b.label}")

    def change_mcdu_unit(self) -> int:
        # To do:
        # 1. Unregister current unit datarefs
        self.device.set_unit_led()
        self.unload_datarefs()
        # 2. Change unit id
        self.device.set_unit_led(on=False)
        self.device.set_unit(MCDU_DEVICE_MASKS.FO if self.device.mcdu_unit & MCDU_DEVICE_MASKS.CAP else MCDU_DEVICE_MASKS.CAP)
        # 3. Register new unit datarefs and wait for data
        self.wait_for_data()
        logger.info(f"MCDU unit {self.device.mcdu_unit_id}")
        self.display._updated.set()
        return self.device.mcdu_unit_id

    def change_aircraft(self, new_icao: str) -> str:
        # To do:
        # 1. Unregister current unit datarefs
        self.device.set_led(led=MCDU_ANNUNCIATORS.STATUS, on=True)
        self.unload_datarefs()
        # 2. Change aircraft
        self.wait_for_toliss_airbus()
        # 3. Load new aircraft datarefs and wait for data
        self.wait_for_data()
        logger.info(f"aircraft is now {self.icao}")
        return self.icao

    def do_key_release(self, key_id: int):
        b = self._buttons_by_id.get(key_id)
        if b is None:
            logger.warning(f"button id {key_id} not found")
            return
        if b.type == ButtonType.SWITCH:
            logger.debug(f"button {b.label} released")
            unit_dataref = self.set_mcdu_unit(b.dataref)
            self.api.set_dataref_value(unit_dataref, 0)
            logger.debug(f"set dataref {unit_dataref} to 0")

    def do_sensors(self, data_in):
        w = False
        v = 256 * int(data_in[18]) + int(data_in[17])
        dl = v - self._left_sensor
        if abs(dl) > self._sensor_delta:
            w = True
            self._left_sensor = v
        v = 256 * int(data_in[20]) + int(data_in[19])
        dr = v - self._right_sensor
        if abs(dr) > self._sensor_delta:
            w = True
            self._right_sensor = v
        if w:
            logger.debug(f"sensors: left {self._left_sensor} ({dl}), right {self._right_sensor} ({dr})")

    def set_brightness(self, dataref, value):
        bl = list(filter(lambda x: x.dataref == dataref, self.buttons))
        if len(bl) == 1:
            b = bl[0]
            if b is not None:
                if b.led is None:
                    logger.debug(f"dataref {dataref} not led")
                    return
                v = max(0, min(value, 255))
                logger.debug(f"led: {b.led}, value: {v}")
                self.device.set_brightness(backlight=b.led, brightness=int(v))
        else:
            logger.warning(f"dataref {dataref} not found")


# ##################
#
# MCDU Display Controller
#
class MCDUTerminal:
    """Character-based display of MCDU content.

    Updated on the console each time the display is refreshed.
    Mainly used for development purpose.

    """

    def display(self, page: list, vertslew_key: int = 0):
        """Create display mock-up on terminal for page returns string.

        Args:
            page (list): Page content
            vertslew_key (int): What slew keys to display on screen content (default: `0`)

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

    def display_page(self, page: list, vertslew_key: int = 0):
        """Create display mock-up on terminal for page returns string.

        Args:
            page (list): Page content
            vertslew_key (int): What slew keys to display on screen content (default: `0`)

        Returns:
            str: characters ready to display, include newlines.
        """
        print("\n")
        for i in range(PAGE_LINES):
            for j in range(PAGE_CHARS_PER_LINE):
                curr = ""
                c = page[i][j * PAGE_BYTES_PER_CHAR : (j + 1) * PAGE_BYTES_PER_CHAR]
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
                    print(MCDU_TERM_COLORS[c[0]], end="")
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
        self.terminal = None  # MCDUColorTerminal()

        self.page = [[" " for _ in range(PAGE_BYTES_PER_LINE)] for _ in range(PAGE_LINES)]
        self.required_datarefs = set()
        self.mcdu_units = set()
        self.datarefs = {}

        self.lines = {}
        self._all_ok = False
        self._last_display = datetime.now()
        self._updated = threading.Event()
        self.update_event = threading.Event()
        self.update_thread = threading.Thread(target=self.update, name="MCDU Screen Updater")
        self.update_thread.start()

    def set_display_datarefs(self, dataref_list: set, mcdu_units: set):
        self.required_datarefs = dataref_list
        self.mcdu_units = mcdu_units

    def clear_page(self):
        self.page = [[" " for _ in range(PAGE_BYTES_PER_LINE)] for _ in range(PAGE_LINES)]

    def clear_lines(self):
        self.lines = {}
        self._all_ok = False

    def startup_screen(self):
        self.device.clear()
        self.clear_page()
        self.write_line_to_page(0, 5, "Winwing  MCDU", MCDU_COLOR.DEFAULT.value)
        self.write_line_to_page(1, 5, "ToLiss Airbus", MCDU_COLOR.DEFAULT.value)
        self.write_line_to_page(2, 6, "for X-Plane", MCDU_COLOR.DEFAULT.value)
        self.write_line_to_page(4, 5, f"version {version}", "G", True)
        self.write_line_to_page(12, 2, "github.com/devleaks", MCDU_COLOR.DEFAULT.value, True)
        self.write_line_to_page(13, 1, "/winwing_toliss_mcdu", MCDU_COLOR.DEFAULT.value, True)

        self.write_line_to_page(8, 1, "waiting for X-Plane...", "A")

        self.device.display_page(page=self.page)

    def waiting_for_data(self):
        self.device.clear()
        self.clear_page()
        self.write_line_to_page(0, 5, "Winwing  MCDU", MCDU_COLOR.DEFAULT.value)
        self.write_line_to_page(1, 5, "ToLiss Airbus", MCDU_COLOR.DEFAULT.value)
        self.write_line_to_page(2, 6, "for X-Plane", MCDU_COLOR.DEFAULT.value)
        self.write_line_to_page(4, 5, f"version {version}", "G", True)
        self.write_line_to_page(12, 2, "github.com/devleaks", MCDU_COLOR.DEFAULT.value, True)
        self.write_line_to_page(13, 1, "/winwing_toliss_mcdu", MCDU_COLOR.DEFAULT.value, True)

        self.write_line_to_page(8, 2, "waiting for data...", "A")

        self.device.display_page(page=self.page)

    def message(self, message, show_heading: bool = True):
        self.device.clear()
        self.clear_page()
        if show_heading:
            self.write_line_to_page(0, 5, "Winwing  MCDU", MCDU_COLOR.DEFAULT.value)
            self.write_line_to_page(1, 5, "ToLiss Airbus", MCDU_COLOR.DEFAULT.value)
            self.write_line_to_page(2, 6, "for X-Plane", MCDU_COLOR.DEFAULT.value)
        self.write_line_to_page(8, 1, message, "A")
        self.device.display_page(page=self.page)

    def write_line_to_page(self, line, pos, text: str, color: str = MCDU_COLOR.DEFAULT.value, font_small: bool = False):
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

    def display(self, page: list | None = None, vertslew_key: int = 0):
        self.device.display_page(page=self.page if page is None else page, vertslew_key=vertslew_key)

    def all_datarefs_available_count(self) -> bool:
        avail_drefs = filter(lambda x: x in self.required_datarefs, self.datarefs)
        return len(list(avail_drefs))

    def all_datarefs_available(self) -> bool:
        return self.all_datarefs_available_count() == len(self.required_datarefs)

    def variable_changed(self, dataref: str, value):
        self.datarefs[dataref] = value

        mcdu_unit = -1
        try:
            m = re.match(MCDU_DISPLAY_DATA, dataref)
            if m is None:
                logger.warning(f"not a display dataref {dataref}")
                return
            mcdu_unit = int(m["unit"])
        except:
            logger.warning(f"error invalid MCDU unit for {dataref}")
            return

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

        # Processing completed
        # is this dataref related to the unit we are currently displaying?
        if mcdu_unit != self.device.mcdu_unit_id:
            # logger.debug(f"{dataref} does not belong to unit on display ({mcdu_unit})")
            return

        if not self.all_datarefs_available():
            # if (len(self.required_datarefs) - self.all_datarefs_available_count()) < 4:
            #     print("still missing", set(self.required_datarefs) - set(self.datarefs.keys()))
            return

        if not self._all_ok:
            logger.debug(f"all {len(self.required_datarefs)} required dataref available")
            self._all_ok = True

        self._updated.set()

    def update(self):
        logger.info("display updater started")
        while not self.update_event.is_set():
            if self._updated.wait(1):
                self._updated.clear()  # we clear first since an update may come while we refresh the display
                self.show_page()
        logger.info("display updater terminated")

    def stop_update(self):
        self.update_event.set()

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
                    v = self.datarefs.get(name)
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
                    v = self.datarefs.get(name)
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

    def show_page(self):
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
                self.page[lnum][pos * PAGE_BYTES_PER_CHAR] = c[1]  # color
                self.page[lnum][pos * PAGE_BYTES_PER_CHAR + 1] = font_small
                self.page[lnum][pos * PAGE_BYTES_PER_CHAR + 2] = c[0]  # char
                pos = pos + 1

        logger.debug(f"page for mcdu unit {self.device.mcdu_unit_id}")

        self.clear_page()
        vertslew_key = self.datarefs.get("AirbusFBW/MCDU1VertSlewKeys", 0)

        show_line(self.lines[f"AirbusFBW/MCDU{self.device.mcdu_unit_id}title"], 0, 0)
        for l in range(1, 7):
            show_line(self.lines[f"AirbusFBW/MCDU{self.device.mcdu_unit_id}label{l}"], 2 * l - 1, 1)
            show_line(self.lines[f"AirbusFBW/MCDU{self.device.mcdu_unit_id}cont{l}"], 2 * l, 0)
        show_line(self.lines[f"AirbusFBW/MCDU{self.device.mcdu_unit_id}sp"], 13, 0)

        # display mcdu on winwing
        self.device.display_page(page=self.page, vertslew_key=vertslew_key)
        if self.terminal is not None:
            self.terminal.display_page(page=self.page, vertslew_key=vertslew_key)


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
