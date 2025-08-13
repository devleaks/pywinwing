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

```sh
pip install 'winwing @ git+https://github.com/devleaks/pywinwing.git'
```


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
  --use-beacon          REMOTE USE ONLY - attempt to use X-Plane UDP beacon to discover network address
  --host HOST           REMOTE USE ONLY - host IP name or address for X-Plane Web API
  --port PORT           TCP port for X-Plane Web API
  --aircraft acf.yaml   DEVELOPER ONLY - uses this aircraft configuration file
  --extension ext_dir [ext_dir ...]
                        DEVELOPER ONLY - adds extension folders to application
```


## Important Note

`winwing-cli` application is stateless.

In case of problem, misbehavior, errors... simply stop the application and restart it.
If problem persists, enter an issue on github.

MCDU display sometimes get de-synchronized.
To re-synchronize it, unplug the Winwing MCDU device for a few seconds and plug it in back.
Restart `winwing-cli`.


# More Devices

The package is a framework that facilitates the addition of devices and aircraft specifics into the same application.

See developer notes on the menu / side bar.