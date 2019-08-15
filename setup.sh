#!/bin/bash

echo
echo -e "+--------------------------------------------------------------------+"
echo -e "| \033[0;34m   .oooooooo.   \033[0m             888                                   |"
echo -e "| \033[0;34m  d8P'    'Y8b  \033[0m   .oooo.    888   .ooooo.  oooo    ooo  .oooo.    |"
echo -e "| \033[0;34m 888        888 \033[0m  'P  )88b   888  d88' '88b  '88b..8P'  'P  )88b   |"
echo -e "| \033[0;34m 888        888 \033[0m   .oP'888   888  888ooo888    Y888'     .oP'888   |"
echo -e "| \033[0;34m '88bb    dd88' \033[0m  d8(  888   888  888    .o  .o8''88b   d8(  888   |"
echo -e "| \033[0;34m  'Y8bb,ood8P'  \033[0m  'Y888888o  888o 'Y8bod8P' o88'   888o 'Y888888o  |"
echo -e "+--------------------------------------------------------------------+"
echo

# update gadget id and secret for all example projects
read -p "Have you registered your Alexa Gadget in the Alexa Developer Portal (y/n)? " -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter the Amazon ID for your gadget: " device_type
    read -p "Enter the Alexa Gadget Secret for your gadget: " device_type_secret
    for f in `find . -name "*.ini"`; do
	sed -i "s/YOUR_GADGET_AMAZON_ID/$device_type/" $f
	sed -i "s/YOUR_GADGET_SECRET/$device_type_secret/" $f
    done
fi

# update and install the latest system updates
sudo apt-get -y update && sudo apt-get -y upgrade

# install necessary bluetooth libraries
sudo apt-get -y install bluetooth bluez libbluetooth-dev libudev-dev python-bluez bluez-hcidump python3-dbus

# Purge A2DP profile to improve connectivity stability, add this back in when we support A2DP
sudo apt-get -y purge bluealsa

# put BlueZ in compatibility mode if it isn't already
sudo sed -i "s/bluetoothd$/bluetoothd --compat/" /etc/systemd/system/bluetooth.target.wants/bluetooth.service

# add user to 'bluetooth' group
sudo usermod -a -G "bluetooth" "$USER"

# install pip
sudo apt-get -y install python3-pip
sudo -H pip3 install --upgrade pip

# install python depdencies
sudo pip3 install pybluez protobuf python-dateutil gpiozero colorzero

# install the agt library
sudo pip3 install -e src

# reboot
echo
echo -e "\033[0;32m+------------------------------+\033[0m"
echo -e "\033[0;32m|            SUCCESS           |\033[0m"
echo -e "\033[0;32m+------------------------------+\033[0m"
echo
read -p "Press any key to reboot to complete setup"
sudo reboot
