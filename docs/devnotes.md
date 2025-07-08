# pywinwing Developer Notes

The content of this file will be transfered to github wiki for information.


## Same host

In normal operations, when everything is connected to the same computer, it is suffisent to type

```
winwing-cli
```

`winwing-cli will try to connect to all devices available on the computer and load the aircraft currently loaded in X-Plane specifics to set the display on devices accordingly.

If a device is not supported, it is ignored.

If a currently loaded aircraft is not adapted for the devices, the aircraft is not loaded.

In both cases, warning messages are issued on the console.


## Remote host

It is possible to use device connected to one computer with X-Plane running on another computer. Winwing-cli must run on the computer where the devices are connected. In this case, winwing-cli will automatically connect the the X-Plane instance it find on the local area network.

Networking options are:

```
winwing-cli --use-beacon
```
Monitors X-Plane UDP beacon to set up network parameters automatically. (The message in the beacon contains the necessary information.)

If no beacon is found, explicit hostname and port can be supplied on command line

```
winwing-cli --host host_with_xplane --port 8080
```
THe port number should be TCP port number of the proxy server installed where X-Plane runs.


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


# Base Classes for adding a new devices or aircraft

- Coordinator (derived from WinwingDevice), which includes connection to X-Plane
- Device adapter (derived from Device or HIDDevice), HID operations to/from the device
- Aircraft adapter (derived from Aircraft): parameters, datarefs, commands, data


# Adding a new Device

Later.
