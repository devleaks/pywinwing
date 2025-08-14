# WINWING Device to X-Plane

Welcome.

The pywinwing package is a python package that aim at interfacing Winwing devices to X-Plane.

# Installation

## HID Library

You must first install a USB HID library.
The installation of this library depends on your operating system.
We recommand using the [hidapi](https://github.com/libusb/hidapi)
widely used and available.

On MacOS, the library is installed by [brew](https://brew.sh) or
port package manager like

```sh
brew install hidapi
```

This library will be used by a python package.

pywinwing uses [this](https://github.com/apmorton/pyhidapi) python package
which appears to be a simple python wrapper around essential hidapi library functions.
Nothing more, nothing less. Couldn't be simpler.

## Python Application

It is advisable to create and use a dedicated python environment.

To install the Winwing application, issue the following command
to install the appropriate python package and its dependencies:

```sh
pip install 'winwing @ git+https://github.com/devleaks/pywinwing.git'
```

Partof the installation of the above package is
the installation of a command that can be executed from the prompt.


# Usage


The installation process creates a new command that can be executed from the prompt
in a terminal window.

```sh
$ winwing-cli --help

usage: winwing-cli [-h] [--version] [-v] [-l] [-a] [--use-beacon] [--host HOST] [--port PORT] [--aircraft acf.yaml] [--extension ext_dir [ext_dir ...]]

Winwing Devices for X-Plane

options:
  -h, --help            show this help message and exit
  --version             shows version information and exit
  -v, --verbose         shows more information
  -l, --list            lists Wingwing devices connected to the system
  -a, --list-all        lists all HID devices connected to the system
  --port PORT           TCP port for X-Plane Web API
  --use-beacon          REMOTE USE ONLY - attempt to use X-Plane UDP beacon to discover network address
  --host HOST           REMOTE USE ONLY - host IP name or address for X-Plane Web API
  --aircraft acf.yaml   DEVELOPER ONLY - uses this aircraft configuration file
  --extension ext_dir [ext_dir ...]
                        DEVELOPER ONLY - adds extension folders to application
```

As a normal use, you can ignore *REMOTE USE ONLY* and *DEVELOPER ONLY* options.


## Important Note

`winwing-cli` application is stateless.

In case of problem, misbehavior, errors... simply stop the application and restart it.
If problem persists, enter an issue on github.

MCDU display sometimes get de-synchronized.
To recognize this state, start `winwing-cli` and nothing will display on the MCDU device,
not even a welcome screen, it will remain black, which is unusual.

To re-synchronize it, unplug the Winwing MCDU device for a few seconds and plug it in back.
Restart `winwing-cli`.

This event is still under investigation and rarely appears, however, I prefer to mention it here.


# More Devices

The package is more that the Winwing application.
It is a framework that facilitates the addition of devices and aircraft specifics into the same application.

See developer notes on the menu / side bar.