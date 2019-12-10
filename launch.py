#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

import apt
import argparse
import dbus
from dbus.mainloop.glib import DBusGMainLoop
import fileinput
import json
from pip._internal.utils.misc import get_installed_distributions
import os
from os import path
import signal
import subprocess
import sys
import tarfile
import urllib

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--setup', action='store_true', required=False,
                    help='Initiates the setup which lets you configure the gadget\'s credentials, '
                         'switch between transport modes, install necessary dependencies.')
parser.add_argument('--example', action='store', required=False,
                    help='Runs the example script represented by the specified example name or path')
parser.add_argument('--pair', action='store_true', required=False,
                    help='(use with --example flag) '
                         'Puts the gadget in pairing/discoverable mode. '
                         'If you are pairing to a previously paired Echo device, '
                         'please ensure that you first forget the gadget from the Echo device '
                         'using the Bluetooth menu in Alexa App or Echo\'s screen.')
parser.add_argument('--clear', action='store_true', required=False,
                    help='(use with --example flag) '
                         'Reset gadget by unpairing bonded Echo device and clear config file. '
                         'Please also forget the gadget from the Echo device using the Bluetooth menu '
                         'in Alexa App or Echo\'s screen. To put the gadget in pairing mode again, use --pair')
args = parser.parse_args()

# setup gadget
initiate_setup = False
first_time_setup = False

global_config_path = path.join(path.join(path.dirname(path.abspath(__file__))), 'src/.agt.json')

# determine if gadget is being setup for the first time
if not os.path.exists(global_config_path):
    first_time_setup = True

# initiate setup if --setup flag is mentioned or if the launch.py script is being run for the first time
if args.setup or first_time_setup:
    initiate_setup = True
    print("+--------------------------------------------------------------------+")
    print("|    .oooooooo.                888                                   |")
    print("|   d8P'    'Y8b     .oooo.    888   .ooooo.  oooo    ooo  .oooo.    |")
    print("|  888        888   'P  )88b   888  d88' '88b  '88b..8P'  'P  )88b   |")
    print("|  888        888    .oP'888   888  888ooo888    Y888'     .oP'888   |")
    print("|  '88bb    dd88'   d8(  888   888  888    .o  .o8''88b   d8(  888   |")
    print("|   'Y8bb,ood8P'    'Y888888o  888o 'Y8bod8P' o88'   888o 'Y888888o  |")
    print("+--------------------------------------------------------------------+\n")

# configure gadget credentials in all example .ini files
if initiate_setup:
    configure_creds = input("Do you want to configure all examples with your Alexa Gadget credentials (y/n)? ").strip()
    if configure_creds.lower() == 'y':
        device_type = input("Enter the Amazon ID for your gadget: ").strip()
        device_type_secret = input("Enter the Alexa Gadget Secret for your gadget: ").strip()

        for pkg_path, pkg_name, file_name_list in os.walk(os.path.dirname(os.path.abspath(__file__)) + "/src/examples"):
            for file_name in file_name_list:
                if file_name.endswith(".ini"):
                    for line in fileinput.input(path.join(pkg_path, file_name), inplace=True):
                        if "amazonId" in line:
                            print('amazonId = {}'.format(device_type))
                        elif "alexaGadgetSecret" in line:
                            print('alexaGadgetSecret = {}'.format(device_type_secret))
                        else:
                            print('{}'.format(line), end='')

# list of necessary apt packages
apt_package_list = ['bluetooth', 'libbluetooth-dev', 'libudev-dev', 'python-bluez',
                    'bluez-hcidump', 'python3-dbus', 'python3-pip', 'libusb-dev', 'libdbus-1-dev',
                    'libglib2.0-dev', 'libical-dev', 'libreadline-dev']

# determine the missing apt packages
# if first time setup, no need to perform this step as all packages will be installed/updated
apt_missing_packages = []
cache = apt.Cache()
if not first_time_setup:
    for package in apt_package_list:
        if not cache[package].is_installed:
            apt_missing_packages.append(package)

# install the apt packages if missing or if first time setup
if len(apt_missing_packages) > 0 or first_time_setup:
    # update and install the latest system updates
    subprocess.run("sudo apt-get -y update && sudo apt-get -y upgrade", shell=True)
    # refresh cache after the update
    cache = apt.Cache()
    # install the packages
    package_list = apt_package_list if first_time_setup else apt_missing_packages
    for package in package_list:
        print("Package {}{} installing...".format(package, " missing," if not first_time_setup else ""))
        cache[package].mark_install()
        try:
            cache.commit()
        except Exception as e:
            print("Package {} wasn't installed: [{}]\n Please try to manually install this package.".format(package, e))
            sys.exit(0)

# install patched bluez 5.50 package if it is first time setup or if version 5.50 is not present
if first_time_setup or not cache['bluez'].is_installed or \
        '5.50' not in subprocess.check_output('dpkg -s bluez | grep -i version', shell=True).decode('ascii'):

    # display the terms and conditions associated with downloading, modifying and installing Bluez-5.50
    TERMS = "\nThe Alexa Gadgets Raspberry Pi launch script provided herein will retrieve the 'Bluez-5.50' package " + \
            "at install-time from third-party sources. There are terms and conditions that you need to agree " + \
            "to abide by if you choose to install the 'Bluez-5.50' package " + \
            "(https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/COPYING?h=5.50). This script will also enable you " + \
            "to modify and install the 'bluez-5.50' package to enable notification callbacks after reconnections to a " + \
            "paired Echo device. This is required for communication between your gadget and the Echo device over BLE. " + \
            "If you do not agree with every term and condition associated with 'Bluez-5.50', " + \
            "enter 'QUIT', else enter 'AGREE'.\n:"

    # if terms and conditions are not agreed, quit the script
    terms_decision = input(TERMS).strip().upper()
    if terms_decision != 'AGREE':
        sys.exit()

    print("Downloading bluez-5.50 and modifying it..")
    # download the bluez-5.50 distribution
    bluez_file_path = path.join(path.join(path.dirname(path.abspath(__file__))), "bluez-5.50.tar.xz")
    urllib.request.urlretrieve("http://www.kernel.org/pub/linux/bluetooth/bluez-5.50.tar.xz", bluez_file_path)
    # extract the contents of the patched bluez-5.50 tar file
    tf = tarfile.open(bluez_file_path)
    tf.extractall()
    bluez_folder_path = bluez_file_path.replace(".tar.xz", "")

    # enable Notification callbacks by commneting out the notification callback condition
    comment_line_number = int(subprocess.check_output("grep -n 'if (ccc->value\[0\] == value\[0\] && ccc->value\[1\] == value\[1\])' {}/src/gatt-database.c | head -n 1 | cut -d: -f1".format(bluez_folder_path), shell=True).decode('ascii'))
    subprocess.run("sed -i '{},{}s/^/\/\//' {}/src/gatt-database.c".format(comment_line_number, comment_line_number+1, bluez_folder_path), shell=True)

    print("Installing modified bluez-5.50...")
    # install the patched bluez-5.50 package
    subprocess.run(
        "cd {} ; ./configure; sudo make; sudo make install".format(bluez_folder_path),
        shell=True)

    # clean the setup files
    subprocess.run("sudo rm -rf {}*".format(bluez_folder_path), shell=True)

# purge A2DP profile to improve connectivity stability
if cache['bluealsa'].is_installed:
    cache['bluealsa'].mark_delete(purge=True)
    try:
        cache.commit()
    except Exception as e:
        print("Package bluealsa wasn't purged: [{}]\n Please try to manually purge this package.".format(e))
        sys.exit(0)

# list of pip packages
pip_package_list = ['pybluez', 'protobuf', 'python-dateutil', 'gpiozero', 'colorzero']

# determine the missing pip packages
# if first time setup, no need to perform this step as all packages will be installed/updated
pip_missing_packages = []
if not first_time_setup:
    installed_packages = {package.project_name.lower(): package.location for package in get_installed_distributions()}
    for package in pip_package_list:
        if package.lower() not in installed_packages.keys():
            pip_missing_packages.append(package)

# install the pip packages if missing or if first time setup
if len(pip_missing_packages) > 0 or first_time_setup:
    # update pip3
    subprocess.run("sudo -H pip3 install --upgrade pip", shell=True)
    # install the packages
    package_list = pip_package_list if first_time_setup else pip_missing_packages
    for package in package_list:
        print("Python3 package {}{} installing...".format(package, " missing," if not first_time_setup else ""))
        subprocess.run("sudo pip3 install {}".format(package), shell=True)

local_agt_path = path.join(path.join(path.dirname(path.abspath(__file__))), 'src')

# install local agt module if missing or if installation path doesn't match
if first_time_setup or 'agt' not in installed_packages.keys() or \
        os.path.dirname(os.path.realpath(__file__)) not in installed_packages['agt']:
    print("'agt' pip module {} installing...".format(" missing," if not initiate_setup else ""))
    subprocess.run("sudo pip3 install -e {}".format(local_agt_path), shell=True)

# configure transport mode
if initiate_setup:
    switch_transport_mode = False

    # if agt module is just installed, it will need to be added to sys.path for the imports ahead to work
    if local_agt_path not in sys.path:
        sys.path.append(local_agt_path)

    # import agt related packages here
    from agt.alexa_gadget import BLE, BT, _TRANSPORT_MODE, _ECHO_BLUETOOTH_ADDRESS
    from agt.base_adapter import BaseAdapter

    transport_mode = None
    echo_bluetooth_address = None

    # if setup being run for the first time, let user choose the transport mode
    if first_time_setup:
        user_input = input("Which transport mode would you like to configure your gadget for (ble/bt)?").strip()
        while user_input.lower() not in [BLE.lower(), BT.lower()]:
            user_input = input(
                "Invalid choice!\nWhich transport mode would you like to configure your gadget for (ble/bt)?").strip()
        switch_transport_to = BLE if user_input.lower() == BLE.lower() else BT

    # else, let user switch the transport mode
    else:
        try:
            # determine the currently configured transport mode
            with open(global_config_path, "r") as read_file:
                data = json.load(read_file)
                transport_mode = data.get(_TRANSPORT_MODE, None)
                echo_bluetooth_address = data.get(_ECHO_BLUETOOTH_ADDRESS, None)
            # if transport mode not configured correctly in the config file, raise exception which would be caught and
            # user will be asked to re-select the transport mode
            if transport_mode not in [BLE, BT]:
                raise Exception
            switch_transport_to = BT if transport_mode == BLE else BLE
            switch_transport_mode = True if input(
                "Your gadget is currently configured to use {} transport mode.\n"
                "Do you want to switch to {} transport mode (y/n)? "
                    .format(transport_mode, switch_transport_to)).strip().lower() == 'y' else False
        except:
            print("Invalid transport mode found in config file!")
            user_input = input("Which transport mode would you like to configure your gadget for (ble/bt)?").strip()
            while user_input.lower() not in [BLE.lower(), BT.lower()]:
                user_input = input(
                    "Invalid choice!\n"
                    "Which transport mode would you like to configure your gadget for (ble/bt)?").strip()
            switch_transport_to = BLE if user_input.lower() == BLE.lower() else BT
            switch_transport_mode = True

    if first_time_setup or switch_transport_mode:
        if switch_transport_mode:
            # first unpair gadget from Echo device
            print("While switching the transport mode, gadget needs to be unpaired from the Echo device.\n" +
                  "Please unpair the gadget from the Echo device using the Bluetooth menu in Alexa App or Echo\'s screen.\n")

            # prompt the user to unpair the gadget from the Echo device
            input("Press ENTER to continue once you've unpaired your gadget from the Echo device.")

            print("Clearing pairing bond from the gadget...")
            # create dummy adapter and use its unpair functions
            try:
                BaseAdapter(dbus.SystemBus(DBusGMainLoop()), dbus).unpair(echo_bluetooth_address)
            except Exception:
                pass

            # remove the Echo device's bt address from the config
            with open(global_config_path, "w+") as write_file:
                write_data = {_ECHO_BLUETOOTH_ADDRESS: None, _TRANSPORT_MODE: transport_mode}
                json.dump(write_data, write_file)

        # put BlueZ in compatibility mode if it isn't already
        subprocess.run(
            'sudo sed -i "s/bluetoothd$/bluetoothd --compat/" /etc/systemd/system/bluetooth.target.wants/bluetooth.service',
            shell=True)

        # add user to 'bluetooth' group
        subprocess.run('sudo usermod -a -G "bluetooth" "$USER"', shell=True)

        # restart Bluetooth daemon
        subprocess.run('sudo systemctl daemon-reload; sudo systemctl restart bluetooth', shell=True)

        # store the transport mode in the config file
        data = {}
        if not first_time_setup:
            with open(global_config_path, "r") as read_file:
                data = json.load(read_file)
        with open(global_config_path, "w+") as write_file:
            data[_TRANSPORT_MODE] = switch_transport_to
            json.dump(data, write_file)


    print("+------------------------------+")
    print("|            SUCCESS           |")
    print("+------------------------------+\n")

# run the example
if args.example is not None:
    # catch the keyboard interrupt for this script and let the example script subprocess exit gracefully
    def keyboard_interrupt_handler(signum, frame):
        print('Keyboard interrupt. Script will terminate soon...')
    signal.signal(signal.SIGINT, keyboard_interrupt_handler)

    flags = "{} {}".format("--clear" if args.clear else "", "--pair" if args.pair else "")
    example_path = path.join(path.join(path.dirname(path.abspath(__file__))),
                             'src/examples/{}'.format(args.example))
    if os.path.exists("{}/{}.py".format(example_path, args.example)):
        subprocess.run("cd {}; python3 {}.py {}".format(example_path, args.example, flags),
                       shell=True)
    elif os.path.exists(args.example):
        subprocess.run("python3 {} {}".format(args.example, flags), shell=True)
    else:
        print("Example script doesn't exist. Please ensure the example name or path is correct.\n" +
              "For e.g. sudo python3 launch.py --example kitchen_sink")
elif not args.setup and not first_time_setup:
    print("No flags specified. Please specify --example or --setup flag.")
    parser.print_help()
