# pywinwing Developer Notes

The package is a framework that facilitates the addition of devices and aircraft specifics into the same application.


# Custom Aircraft

A Winwing Aircraft is an entity that encapsulate aircraft specifics.

There are two parts to an aircraft.

1. An optional python class, derived from `Aircraft` class.
2. An accompagnying configuration data file, containing data for the above class (list of dataref to fetch, commands to issue, etc.)


## Custom Aircraft Class

Later.

## Custom Configuration Data File

If a developer want to collect the requirements to support a new aircraft, the developer can temporary load a specific aircraft configuration. This is accomplished with the —aircraft flag:

winwing-cli —aircraft devfile.yaml

In this case, winwing-cli will cancel its ability to change aircraft when the user changes the aircraft in X-Plane.
A warning message will be sent accordingly.

In all case, an Aicraft Adapter must already exist for that aircraft to handle aicraft specifics.


### About Aircraft Configuration File

The ACF specifies aircraft specific parameters necessary to make the device work as expected.

ACF files are Yaml formatted files. Yaml is a highly human readable format. It consists of structured name: value pairs, where the value can by a number, text, a list of values, or another list of name: value pairs.


## pywinwing Future

When an aircraft is proven working, it can be included in pywinwing standard distribution.

Please submit a pull request on github to do so.


# Adding a new Winwing Device

Winwing Devices are derived from the python WinwingDevice class.
A WinwingDevice has a "hardware adapter" (device driver) that reads "messages" sent by the hardware device
and transmit them to the application through a Device Report instance.
Upon receipt of a Report, the application executes the appropriate Action.

Aircraft specifics are derived from a python Aircraft class.
The Aircraft class has the ability to read a configuration file to customize its behavior.
In X-Plane, Aircraft are identified by their ICAO code and their author(s) name(s).
Additionnally, there is room for a "variant" additional attribute. (NEO engine variants, configurations, etc.)

Communication with the simulator is offered through the [X-Plane Web API](https://devleaks.github.io/xplane-webapi/) python package.
The application receives "messages" sent by the simulator through a Simulator Report instance.

For developer, the Winwing package has a structure ready for extensibility.
New device packages are added to `winwing.devices`.
New device or aircraft configuration files are added to `winwing.assets`.

Main class is `winwing.devices.WinwingDevice`;
helper classes are in `winwing.helpers`: `Action`, `Report`, and `Aircraft`.

Winwing Application provides the following:

- A HIDDevice hardware adapter
- A MCDU device handler, which works for several Airbus aircraft
- A MCDU aircraft handler for ToLiss Airbus and Laminar 'stock' Airbus (A330-200)

The handler for ToLiss Airbus has aircraft configuration files for
- A321, A21N,
- A330-900,
- Flight Factor and ToLiss A350-900
It shouldn't be difficult to add configuration files for other ToLiss aircrafts
(A319, A320neo, and forthcoming A320 ceo, and may be A340-600.)
