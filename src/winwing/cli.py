import sys
import os
import logging
import argparse
import pprint
import pathlib
from typing import List

import importlib
import pkgutil


import hid
from xpwebapi import ws_api, beacon

from winwing import version
from winwing.devices import WinwingDevice
from .device_manager import DeviceManager

FORMAT = "[%(asctime)s] %(levelname)s %(threadName)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="%H:%M:%S")

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


parser = argparse.ArgumentParser(description="Winwing Devices for X-Plane")
parser.add_argument("--version", action="store_true", help="shows version information and exit")
parser.add_argument("-v", "--verbose", action="store_true", help="shows more information")
parser.add_argument("-l", "--list", action="store_true", help="lists Wingwing devices connected to the system")
parser.add_argument("-a", "--list-all", action="store_true", help="lists all HID devices connected to the system")
parser.add_argument("--use-beacon", action="store_true", help="REMOTE USE ONLY - attempt to use X-Plane UDP beacon to discover network address")
parser.add_argument("--host", nargs=1, help="REMOTE USE ONLY - host IP name or address for X-Plane Web API", default="127.0.0.1")
parser.add_argument("--port", nargs=1, type=int, help="TCP port for X-Plane Web API", default=8086)
parser.add_argument("--aircraft", nargs=1, type=pathlib.Path, metavar="acf.yaml", help="DEVELOPER ONLY - uses this aircraft configuration file")
parser.add_argument("--extension", nargs="+", type=pathlib.Path, metavar="ext_dir", help="DEVELOPER ONLY - adds extension folders to application")

args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.DEBUG)

if args.version:
    print(version)
    os._exit(0)


def print_device(d):
    if d["vendor_id"] == 0 and d["product_id"] == 0:
        return
    if args.verbose:
        pprint.pprint(device)
    else:
        print(f"{d['manufacturer_string']} {d['product_string']} (vendor id={d['vendor_id']}, product id={d['product_id']})")


if args.list_all:
    shown = set()
    for device in hid.enumerate():
        k = (device["vendor_id"], device["product_id"])
        if k not in shown:
            shown.add(k)
            print_device(device)
    os._exit(0)

if args.list:
    first = True
    device_list = hid.enumerate()
    if len(device_list) > 0:
        for device in hid.enumerate():
            if device["vendor_id"] in WinwingDevice.WINWING_VENDOR_IDS:
                if first:
                    first = False
                #     print(f"devices for vendor {device['manufacturer_string']} (id={device['vendor_id']})")
                print_device(device)
        if first:
            print(f"no hid device for vendor identifier(s) {', '.join([str(i) for i in WinwingDevice.WINWING_VENDOR_IDS])}")
    else:
        print("no hid device")
    os._exit(0)


def add_extensions(extension_paths: List[str], trace_ext_loading: bool = False):
    # https://stackoverflow.com/questions/3365740/how-to-import-all-submodules
    all_extensions = set()

    def import_submodules(package, recursive=True):
        """Import all submodules of a module, recursively, including subpackages

        :param package: package (name or actual module)
        :type package: str | module
        :rtype: dict[str, types.ModuleType]
        """
        if isinstance(package, str):
            try:
                if trace_ext_loading:
                    logger.info(f"loading package {package}")
                package = importlib.import_module(package)
            except ModuleNotFoundError:
                logger.warning(f"package {package} not found, ignored")
                return {}

        results = {}
        for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
            full_name = package.__name__ + "." + name
            try:
                results[full_name] = importlib.import_module(full_name)
                if trace_ext_loading:
                    logger.info(f"loading module {full_name}")
            except ModuleNotFoundError:
                logger.warning(f"module {full_name} not found, ignored", exc_info=True)
                continue
            except:
                logger.warning(f"module {full_name}: error", exc_info=True)
                continue
            if recursive and is_pkg:
                results.update(import_submodules(full_name))
        return results

    if extension_paths is not None:
        for path in extension_paths:
            pythonpath = os.path.abspath(path)
            if os.path.exists(pythonpath) and os.path.isdir(pythonpath):
                if pythonpath not in sys.path:
                    sys.path.append(pythonpath)
                    arr = os.path.split(pythonpath)
                    all_extensions.add(arr[1])
                    if trace_ext_loading:
                        logger.info(f"added extension path {pythonpath} to sys.path")

    logger.debug(f"loading extensions {", ".join(all_extensions)}..")
    loaded = []
    for package in all_extensions:
        test = import_submodules(package)
        if len(test) > 0:
            logger.debug(f"loaded package {package}")  #  (recursively)
            loaded.append(package)
    logger.debug("..loaded")
    logger.info(f"loaded extensions {", ".join(loaded)}")

if args.extension is not None and len(args.extension) > 0:
    add_extensions(extension_paths=args.extension, trace_ext_loading=True)

def main():
    if args.verbose:
        print(f"options {args}")

    winwing_devices = DeviceManager.enumerate()
    if len(winwing_devices) == 0:
        print("no Winwing device detected")
        return

    probe = None
    api = None

    if args.use_beacon:
        probe = beacon()
        api = ws_api()
        probe.set_callback(api.beacon_callback)
        probe.start_monitor()
    else:
        host = args.host[0] if type(args.host) is list else args.host
        port = args.port[0] if type(args.port) is list else args.port
        if args.verbose:
            print(f"api at {host}:{port}")
        api = ws_api(host=host, port=port)

    try:
        for winwing_device in winwing_devices:
            winwing_device.set_api(api)
            if args.aircraft is not None:
                winwing_device.set_aircraft_configuration(args.aircraft[0])
            if args.extension is not None and len(args.extension) > 0:
                winwing_device.set_extension_paths(args.extension)

            winwing_device.run()
    except KeyboardInterrupt:
        for winwing_device in winwing_devices:
            winwing_device.terminate()
        if api is not None:
            api.disconnect()
        if probe is not None:
            probe.stop_monitor()


if __name__ == "__main__":
    main()
