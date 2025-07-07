# Developer Notes

The content of this file will be transfered to github wiki for information.


In normal operations, when everything is connected to the same computer, it is suffisent to type

```
winwing-cli
```

`winwing-cli will try to connect to all devices available on the computer and load the aircraft currently loaded in X-Plane specifics to set the display on devices accordingly.

If a device is not supported, it is ignored.

If a currently loaded aircraft is not adapted for the devices, the aircraft is not loaded.

In both cases, warning messages are issued on the console.

# Custom Aircraft

If a developer want to collect the requirements to support a new aircraft, the developer can temporary load a specific aircraft configuration. This is accomplished with the —aircraft flag:

winwing-cli —aircraft devfile.yaml

In this case, winwing-cli will cancel its ability to change aircraft when the user changes the aircraft in X-Plane. A warning message will be sent accordingly.

# Remote Access

It is possible to use device connected to one computer with X-Plane running on another computer. Winwing-cli must run on the computer where the devices are connected. In this case, winwing-cli will automatically connect the the X-Plane instance it find on the local area network.

Networking options are:

```
—beacon
```
Monitors X-Plane UDP beacon to set up network parameters automatically. (The message in the beacon contains the necessary information.)

```
—host, —port
```
Specify X-Plane host name or IP address and TCP port number for the remote API.

The above two options are mutually exclusive. If beacon is used, host and port are ignored.

# Aircraft Configuration File

The ACF specifies aircraft specific parameters necessary to make the device work as expected.

ACF files are Yaml formatted files. Yaml is a highly human readable format. It consists of structured name: value pairs, where the value can by a number, text, a list of values, or another list of name: value pairs.

# Base Classes

- Coordinator, which includes connection to X-Plane
- Device driver, HID operations to/From the device
- Aircraft abstraction: parameters, datarefs, commands, data
