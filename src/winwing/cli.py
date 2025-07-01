import os
import logging
import argparse
import pprint

import hid
from xpwebapi import ws_api

from winwing import version
from .device_manager import WINWING_VENDOR_IDS, DeviceManager

FORMAT = "[%(asctime)s] %(levelname)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="%H:%M:%S")

parser = argparse.ArgumentParser(description="Winwing MCDU for X-Plane")
parser.add_argument("--version", action="store_true", help="show version information and exit")
parser.add_argument("-v", "--verbose", action="store_true", help="show more information")
parser.add_argument("-l", "--list", action="store_true", help="list Wingwing devices connected to the system")
parser.add_argument("-a", "--list-all", action="store_true", help="list all HID devices connected to the system")
parser.add_argument("--host", nargs=1, help="Host IP name or address for X-Plane Web API", default="127.0.0.1")
parser.add_argument("--port", nargs=1, help="TCP port for X-Plane Web API", default=8086)

args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.DEBUG)

if args.version:
    print(version)
    os._exit(0)

if args.list_all:
    for device in hid.enumerate():
        pprint.pprint(device)
    os._exit(0)

if args.list:
    for device in hid.enumerate():
        if device["vendor_id"] in WINWING_VENDOR_IDS:
            pprint.pprint(device)
    os._exit(0)


def main():
    if args.verbose:
        print(f"options {args}")
    host = args.host[0] if type(args.host) is list else args.host
    port = args.port[0] if type(args.port) is list else args.port
    if args.verbose:
        print(f"api at {host}:{port}")
    api = ws_api(host=host, port=port)

    winwing_devices = DeviceManager.enumerate()
    if len(winwing_devices) > 0:
        for winwing_device in winwing_devices:
            winwing_device.set_api(api)
            winwing_device.run()
    else:
        print(f"no Winwing device detected")


if __name__ == "__main__":
    main()
