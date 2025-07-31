from abc import ABC


class Action(ABC):

    def __init__(self, name: str) -> None:
        self.name = name

class DeviceAction(Action):

    def __init__(self, name: str, device) -> None:
        Action.__init__(self, name=name)
        self.device = device

class SimulatorAction(Action):

    def __init__(self, name: str, simulator) -> None:
        Action.__init__(self, name=name)
        self.simulator = simulator


class Report(ABC):

    def __init__(self, name: str) -> None:
        self.name = name

class DeviceReport(Report):

    def __init__(self, name: str, device) -> None:
        Report.__init__(self, name=name)
        self.device = device

class SimulatorReport(Report):

    def __init__(self, name: str, simulator) -> None:
        Report.__init__(self, name=name)
        self.simulator = simulator
