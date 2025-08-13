# pywinwing Remote Usage

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
