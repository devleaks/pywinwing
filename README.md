# pywinwing - Winwing Devices to X-Plane


This script allows Winwings unit to work with Laminar Research X-Plane Flight Simulator.

Devices supported by this script will 


# Installation

It is advisable to create and use a dedicated python environment.

```sh
pip install 'winwing @ git+https://github.com/devleaks/pywinwing.git'
```


# Execution


The installation process creates a new command that can be executed from the prompt
in a terminal window.


```
$ winwing-cli --help

usage: winwing-cli [-h] [--version] [-v] [-l] [-a] [--host HOST] [--port PORT] [--aircraft acf.yaml]

Winwing Devices for X-Plane

options:
  -h, --help           show this help message and exit
  --version            show version information and exit
  -v, --verbose        show more information
  -l, --list           list Wingwing devices connected to the system
  -a, --list-all       list all HID devices connected to the system
  --host HOST          Host IP name or address for X-Plane Web API
  --port PORT          TCP port for X-Plane Web API
  --aircraft acf.yaml  Use this aircraft configuration file
```


# Usage

Application will switch aircraft if you do.

If no suitable aircraft is found for the device, it will display _waiting for aircraft..._
on the MCDU display.

This script only allows for known (devices, aircrafts) combination.


# Important Note

`winwing-cli` application is stateless.

In case of problem, misbehavior, errors... simply stop the application and restart it.
If problem persists, enter an issue on github.

Display sometimes get de-synchronized.
To re-synchronize it, unplug the Winwing MCDU device for a few seconds and plug it in back.
Restart `winwing-cli`.


# Future

Works and tested with the following Winwing devices and listed aircrafts:

- [MCDU](https://winwingsim.com/view/goods-details.html?id=945)
    - ToLiss [A321](https://store.x-plane.org/Airbus-A321-XP12-by-Toliss_p_1632.html)+[neo option](https://store.x-plane.org/A321-NEO-ADD-ON-to-the-ToLiss-Airbus-A321_p_1351.html)
    - ToLiss [A330-900](https://store.x-plane.org/Airbus-A330-900-neo%C2%A0by%C2%A0ToLiss_p_1952.html)
    - Flight Factor [A350-900](https://store.x-plane.org/Airbus-A350-XWB-Advanced-for-X-Plane-12-11_p_348.html)
    - Laminar Research [A330-300](https://www.x-plane.com/aircraft/airbus-a330-300/)

This development is a proof of concept and will be enhanced to work with other Winwing devices and other aircrafts.
To test it, one obviously needs to own both the device and the aircraft.


# Development

The pywinwing package is a *framework* that allows for inclusion of
  - more Winwing devices
  - more aircrafts
for existing or new devices.

Please refer to the technical wiki for more information on the framework.

Last updated July 2025

