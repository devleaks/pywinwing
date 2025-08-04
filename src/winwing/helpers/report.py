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
