# pywinwing - Winwing Devices to X-Plane


This script allows Winwings unit to work with Laminar Research X-Plane Flight Simulator.


# Installation

```sh
pip install 'pywinwing @ git+https://github.com/devleaks/pywinwing.git'
```

# Execution

```
$ winwing-cli --help

usage: winwing-cli [-h] [--version] [-v] [-l] [-a] [--host HOST] [--port PORT]

Winwing MCDU for X-Plane

options:
  -h, --help      show this help message and exit
  --version       show version information and exit
  -v, --verbose   show more information
  -l, --list      list Wingwing devices connected to the system
  -a, --list-all  list all HID devices connected to the system
  --host HOST     Host IP name or address for X-Plane Web API
  --port PORT     TCP port for X-Plane Web API

```

Works and tested with the following Winwing devices and listed aircrafts:

- MCDU
    - ToLiss A321+neo option
    - ToLiss A330-900
    - Flight Factor A350-900

This development is a proof of concept and will be enhanced to work with other Winwing devices and other aircrafts.


LAst updated July 2025