"""Action and Report base classes

A device or the simulator sends a report (name loosely inspired by HID protocol).
Reports have a "type", and depending on their type, carry information or value they transfer.
That's what this file attempts to show.

Device reports are sent by HID device. They carry some information. For example, a "key-pressed"
report is issued when a key is pressed, and the information it carries it the name or identifier
of the key that was pressed.
This file explain what must be done when that report is received: the action that must be carried over.

Similarly, the simulator also sends messages on the Web socket, reflecting simulator variable changes,
or executed commands.
In turn, these simulator-reports trigger actions on the device: refresh the display (set-display),
turn this LED on or off, adjust screen brightness or keyboard backlight...
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

from ..devices.winwing import WinwingDevice


# #######################################@
# ACTIONS
#
#
class Action(ABC):

    def __init__(self, name: str, config: dict) -> None:
        self.name = name
        self.config = config

    @abstractmethod
    def execute(self, **kwargs):
        raise NotImplementedError


class DeviceAction(Action):

    def __init__(self, name: str, config: dict, device: WinwingDevice) -> None:
        Action.__init__(self, name=name, config=config)
        self.device = device


class SimulatorAction(Action):

    def __init__(self, name: str, config: dict, simulator) -> None:
        Action.__init__(self, name=name, config=config)
        self.simulator = simulator


# #######################################@
# REPORTS
#
#
class Report(ABC):

    def __init__(self, name: str, key: str, action: Action) -> None:
        """Exchange report

        Args:
            name (str): Name of report, documentation
            key (str): Access key of report, used to identify it
        """
        self.name = name
        self.key = key
        self.action = action

    def activate(self, **kwargs):
        if self.action is None:
            logger.warning(f"no action for {self.name} key={self.key}")
            return

        try:
            self.action.execute(**kwargs)
        except:
            logger.warning(f"issue during action of {self.name} (key={self.key}), report {type(self)}, action={type(self.action)}", exc_info=True)
        return


class DeviceReport(Report):
    """Report produced by a device"""

    def __init__(self, name: str, key: str, action: Action) -> None:
        Report.__init__(self, name=name, key=key, action=action)


class SimulatorReport(Report):
    """Report produced by a simulator"""

    def __init__(self, name: str, key: str, action: Action) -> None:
        Report.__init__(self, name=name, key=key, action=action)
