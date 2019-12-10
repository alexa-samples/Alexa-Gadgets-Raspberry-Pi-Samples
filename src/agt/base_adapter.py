#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#
import logging.config

BUS_NAME = 'org.bluez'
ADAPTER_INTERFACE = 'org.bluez.Adapter1'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'
DEVICE_INTERFACE = 'org.bluez.Device1'

logger = logging.getLogger(__name__)
"""
Base BluetoothAdapter bluetooth interface for Alexa Gadgets application
that contains operations common to both Classic and BLE adapter
"""
class BaseAdapter:

    def __init__(self, bus, dbus):
        # initialize bluez adapter
        self._bus = bus
        self._dbus = dbus
        self.bluez_adapter = self._create_bluez_adapter()

    def _create_bluez_adapter(self):
        objs = self._dbus.Interface(self._bus.get_object(BUS_NAME, '/'), DBUS_OM_IFACE).GetManagedObjects()
        for path, _interface in objs.items():
            adapter = _interface.get(ADAPTER_INTERFACE)
            if adapter is None:
                continue
            # use the first adapter which is the default adapter
            # this means we only support one bt adapter
            return self._dbus.Interface(self._bus.get_object(BUS_NAME, path), ADAPTER_INTERFACE)
        return None

    def _find_device(self, bd_addr):
        objs = self._dbus.Interface(self._bus.get_object(BUS_NAME, '/'), DBUS_OM_IFACE).GetManagedObjects()
        for path, _interface in objs.items():
            device = _interface.get(DEVICE_INTERFACE)
            if device is None:
                continue
            if device['Address'] == bd_addr:
                return self._dbus.Interface(self._bus.get_object(BUS_NAME, path), DEVICE_INTERFACE)
        return None

    def is_paired_to_address(self, bd_addr):
        device = self._find_device(bd_addr)
        if device is None:
            return False
        return True

    def unpair(self, bd_addr):
        device = self._find_device(bd_addr)
        if device is not None:
            self.bluez_adapter.RemoveDevice(device.object_path)
        else:
            logger.info('Device is not paired with Raspberry Pi')