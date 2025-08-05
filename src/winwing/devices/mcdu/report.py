import logging
from typing import Annotated
from enum import Enum

from winwing.devices.winwing import WinwingDevice

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from xpwebapi import Command

from .constant import ICAO_DATAREF, AUTHOR_DATAREF, MCDU_BRIGHTNESS, MCDU_BRIGHTNESS_NAME
from ...helpers.report import DeviceAction, SimulatorAction, DeviceReport, SimulatorReport


# #######################################@
# ACTIONS
#
#
class DEVICE_ACTION(Enum):
    REFRESH_DISPLAY: Annotated[str, "Refresh MCDU display"] = "refresh-display"
    SET_VALUE: Annotated[str, "Set device brightness"] = "set-device-value"
    SET_LED: Annotated[str, "Turn device LED on or off"] = "set-device-led"
    CHANGE_AIRCRAFT: Annotated[str, "Change aircraft base on ICAO code and author"] = "change-aircraft"


class SIMULATOR_ACTION(Enum):
    EXECUTE_COMMAND = "execute-simulator-command"
    SET_VALUE = "set-simulator-value"
    CHANGE_MCDU_UNIT = "change-mcdu-unit"


# ====================
# Device
#
class MCDUDeviceAction(DeviceAction):

    def __init__(self, name: str, config: dict, device) -> None:
        DeviceAction.__init__(self, name=name, config=config, device=device)

    @staticmethod
    def new(config: dict, device: WinwingDevice):
        action = config.get("action")
        if action is None:
            logger.warning(f"no action ({config})")
            return None
        if action == DEVICE_ACTION.REFRESH_DISPLAY.value:
            return RefreshDeviceDisplay(name=config.get("simulator-value-name"), config=config, device=device)
        if action == DEVICE_ACTION.SET_VALUE.value:
            return SetDeviceValue(name=config.get("device-value-name"), config=config, device=device)
        if action == DEVICE_ACTION.SET_LED.value:
            return SetDeviceLed(name=config.get("device-led-name"), config=config, device=device)
        if action == DEVICE_ACTION.CHANGE_AIRCRAFT.value:
            return ChangeAircraft(name=config.get("simulator-value-name"), config=config, device=device)
        return None


class RefreshDeviceDisplay(MCDUDeviceAction):

    def __init__(self, name: str, config: dict, device) -> None:
        MCDUDeviceAction.__init__(self, name=name, config=config, device=device)

    def execute(self, **kwargs):
        if self.device.aircraft is None:
            logger.warning("no aircraft")
            return
        dataref = self.config.get("simulator-value-name")
        value = kwargs.get("value")
        self.device.display.variable_changed(dataref=dataref, value=value)


class SetDeviceValue(MCDUDeviceAction):

    def __init__(self, name: str, config: dict, device) -> None:
        MCDUDeviceAction.__init__(self, name=name, config=config, device=device)

    def execute(self, **kwargs):
        def doit(v, name):
            v100 = int(round(100 * (v + 1) / 256))
            if name == MCDU_BRIGHTNESS_NAME.BACKLIGHT.value:
                self.device.device.set_brightness(backlight=MCDU_BRIGHTNESS.BACKLIGHT, brightness=v)
                logger.info(f"{self.name} set device backlight to {v100}%")
            elif name == MCDU_BRIGHTNESS_NAME.SCREEN_BACKLIGHT.value:
                self.device.device.set_brightness(backlight=MCDU_BRIGHTNESS.SCREEN_BACKLIGHT, brightness=v)
                logger.info(f"{self.name} set device screen backlight to {v100}%")
            else:
                logger.warning(f"{self.name} not a device brightness variable name")

        value = kwargs.get("value")
        if value is None:
            logger.warning(f"{self.name}: value is none")
            return
        if value <= 1:  # dataref is in [0..1], we need [0..255]
            value = int(value * 255)
        value = int(max(0, min(value, 255)))
        varname = self.config.get("device-value-name")
        # if varname is None...
        dataref = self.config.get("simulator-value-name")
        if self.device.brightness.get(dataref, -1) != value:
            self.device.brightness[dataref] = value
            doit(v=value, name=varname)
        # else value not changed


class SetDeviceLed(MCDUDeviceAction):

    def __init__(self, name: str, config: dict, device) -> None:
        MCDUDeviceAction.__init__(self, name=name, config=config, device=device)

    def execute(self, **kwargs):
        mcdu = kwargs.get("mcdu")
        if mcdu is None:
            logger.warning(f"{self.name}: no MCDU device")
            return
        value = kwargs.get("value")
        if value is None:
            logger.warning(f"{self.name}: value is none")
            return

        name = self.config.get("device-value-name")


class ChangeAircraft(MCDUDeviceAction):

    def __init__(self, name: str, config: dict, device) -> None:
        MCDUDeviceAction.__init__(self, name=name, config=config, device=device)

    def execute(self, **kwargs):
        mcdu = kwargs.get("mcdu")
        if mcdu is None:
            logger.warning("no MCDU device")
            return
        dataref = self.config.get("simulator-value-name")
        value = kwargs.get("value")
        if self.device.aircraft is not None:
            self.device.new_acf[dataref] = value
            logger.debug(f"got new aircraft: {dataref}={value}")
            if self.device.new_acf.get(AUTHOR_DATAREF) is not None and self.device.new_acf.get(ICAO_DATAREF) is not None:  # not thread safe
                if self.device.new_acf.get(AUTHOR_DATAREF) != self.device.author or self.device.new_acf.get(ICAO_DATAREF) != self.device.icao:
                    logger.debug("got new icao and/or author, changing aircraft")
                    self.device.change_aircraft(new_author=self.device.new_acf.get(AUTHOR_DATAREF), new_icao=self.device.new_acf.get(ICAO_DATAREF))
                    self.device.new_acf = {}


# ====================
# Simulator
#
class MCDUSimulatorAction(SimulatorAction):

    def __init__(self, name: str, config: dict, simulator) -> None:
        SimulatorAction.__init__(self, name=name, config=config, simulator=simulator)

    @staticmethod
    def new(config: dict, simulator):
        action = config.get("action")
        if action is None:
            logger.warning(f"no action ({config})")
            return None
        if action == SIMULATOR_ACTION.EXECUTE_COMMAND.value:
            return ExecuteSimulatorCommand(name=config.get("simulator-command-name"), config=config, simulator=simulator)
        if action == SIMULATOR_ACTION.SET_VALUE.value:
            return SetSimulatorValue(name=config.get("simulator-value-name"), config=config, simulator=simulator)
        if action == SIMULATOR_ACTION.CHANGE_MCDU_UNIT.value:
            return ChangeMCDUUnit(name=config.get("simulator-value-name"), config=config, simulator=simulator)
        return None


class ChangeMCDUUnit(MCDUSimulatorAction):

    def __init__(self, name: str, config: dict, simulator) -> None:
        MCDUSimulatorAction.__init__(self, name=name, config=config, simulator=simulator)

    def execute(self, **kwargs):
        mcdu = kwargs.get("mcdu")
        if mcdu is None:
            logger.warning("no MCDU device")
            return
        new_unit = mcdu.change_mcdu_unit()
        logger.debug(f"set mcdu unit {new_unit}")


class ExecuteSimulatorCommand(MCDUSimulatorAction):

    def __init__(self, name: str, config: dict, simulator) -> None:
        MCDUSimulatorAction.__init__(self, name=name, config=config, simulator=simulator)

    def execute(self, **kwargs):
        mcdu = kwargs.get("mcdu")
        if mcdu is None:
            logger.warning("no MCDU device")
            return
        unit_dataref = mcdu.aircraft.set_mcdu_unit(str_in=self.name, mcdu_unit=mcdu.device.mcdu_unit_id)
        c = Command(api=self.simulator, path=unit_dataref)
        c.execute()
        logger.debug(f"sent command {unit_dataref}")


class SetSimulatorValue(MCDUSimulatorAction):

    def __init__(self, name: str, config: dict, simulator) -> None:
        MCDUSimulatorAction.__init__(self, name=name, config=config, simulator=simulator)

    def execute(self, **kwargs):
        mcdu = kwargs.get("mcdu")
        if mcdu is None:
            logger.warning("no MCDU device")
            return
        unit_dataref = mcdu.aircraft.set_mcdu_unit(str_in=self.name, mcdu_unit=mcdu.device.mcdu_unit_id)
        value = mcdu.api.get_dataref_value(unit_dataref)
        if value is None:
            logger.debug(f"no value for {unit_dataref} ({value})")
            return
        self.simulator.set_dataref_value(unit_dataref, value)


# #######################################@
# REPORTS
#
#
class DEVICE_REPORT(Enum):
    VALUE_CHANGED = "device-value-change"
    KEY_PRESS = "key-press"


class SIMULATOR_REPORT(Enum):
    VALUE_CHANGED = "simulator-value-change"
    COMMAND_ACTIVE = "simulator-command-active"


# ====================
# Device
#
class MCDUDeviceReport(DeviceReport):

    def __init__(self, name: str, key: str, action) -> None:
        DeviceReport.__init__(self, name=name, key=key, action=action)

    @staticmethod
    def new(config: dict, simulator):
        report_type = config.get("report-type")
        if report_type is None:
            logger.warning(f"no report type ({config})")
            return None
        action = MCDUSimulatorAction.new(config=config, simulator=simulator)
        if action is not None:
            if report_type == DEVICE_REPORT.KEY_PRESS.value:
                return OnDeviceKeyPress(name=config.get("key-name"), key=config.get("key-index"), action=action)
            if report_type == DEVICE_REPORT.VALUE_CHANGED.value:
                return OnDeviceValueChange(name=config.get("device-value-name"), key=config.get("device-value-index"), action=action)
        else:
            logger.warning(f"no action ({config})")


class OnDeviceKeyPress(MCDUDeviceReport):

    def __init__(self, name: str, key: str, action) -> None:
        MCDUDeviceReport.__init__(self, name=name, key=key, action=action)
        self.action = action


class OnDeviceValueChange(MCDUDeviceReport):

    def __init__(self, name: str, key: str, action) -> None:
        MCDUDeviceReport.__init__(self, name=name, key=key, action=action)
        self.action = action


# ====================
# Simulator
#
class MCDUSimulatorReport(SimulatorReport):

    def __init__(self, name: str, key: str, action) -> None:
        SimulatorReport.__init__(self, name=name, key=key, action=action)

    @staticmethod
    def new(config: dict, device: WinwingDevice):
        report_type = config.get("report-type")
        if report_type is None:
            logger.warning(f"no report type ({config})")
            return None
        action = MCDUDeviceAction.new(config=config, device=device)
        if action is not None:
            if report_type == SIMULATOR_REPORT.VALUE_CHANGED.value:
                return OnSimulatorValueChange(name=config.get("simulator-value-name"), key=config.get("simulator-value-name"), action=action)
            if report_type == SIMULATOR_REPORT.COMMAND_ACTIVE.value:
                return OnSimulatorCommandActive(name=config.get("simulator-command-name"), key=config.get("simulator-command-name"), action=action)
        else:
            logger.warning(f"no action ({config})")


class OnSimulatorValueChange(MCDUSimulatorReport):

    def __init__(self, name: str, key: str, action) -> None:
        MCDUSimulatorReport.__init__(self, name=name, key=key, action=action)


class OnSimulatorCommandActive(MCDUSimulatorReport):

    def __init__(self, name: str, key: str, action) -> None:
        MCDUSimulatorReport.__init__(self, name=name, key=key, action=action)
