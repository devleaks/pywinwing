# pywinwing - Winwing Devices to X-Plane


The installation process creates a new command that can be executed from the prompt in a terminal window.


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


# Everything on same computer (simplest, most common case)

If Winwing devices are connected to the computer running X-Plane, issue:

```
winwing-cli
```

The application will start, connect to X-Plane locally and start managing the device.


# Use with Two Computers

If your winwing devices are connected to another computer than the one running X-Plane,
they can be used by issuing

```
winwing-cli --use-beacon
```

provided you allowed X-Plane to send the beacon, and are on the same local area network.

Alternatively, without a beacon, hostname and TCP port number where to contact X-Plane can be
supplied on the command line:

```
winwing-cli --host host_where_xplane --port 8080
```

The application will try to connect to the supplied (hostname, port) and collect data
from X-Plane Web API.


# Important Note

`winwing-cli` application is stateless.

In case of problem, misbehavior, errors... simply stop the application and restart it.
If problem persists, enter an issue on github.

In rare occation, display get de-synchronized, does not display properly, lines appears to be mixed,
or display no longer changes. Issue is under investigation and rarely occurs.
To re-synchronize it, stop `winwing-cli`,
unplug the Winwing MCDU device for a few seconds and plug it in back.
Restart `winwing-cli`.


# Usage Notes

Application will switch aircraft if you do change aircraft in X-Plane.

If no suitable aircraft is found for the device, it will display _waiting for aircraft..._
on the MCDU display.

This script only allows for known (devices, aircrafts) combination.


# Development

The pywinwing package is a *framework* that allows for inclusion of
  - more Winwing devices
  - more aircrafts
for existing or new devices.

Please refer to the technical wiki for more information on the framework.

Last updated July 2025
