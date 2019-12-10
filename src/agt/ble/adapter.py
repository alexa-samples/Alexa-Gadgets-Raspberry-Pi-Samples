#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

import dbus
import dbus.service
import os
import dbus.exceptions
import logging.config
from dbus.mainloop.glib import DBusGMainLoop
import time
import codecs
import subprocess
from agt.ble.protocol import BLEProtocol, Packetizer
from agt.base_adapter import BaseAdapter
from agt.base_adapter import BUS_NAME, ADAPTER_INTERFACE, DBUS_OM_IFACE, DEVICE_INTERFACE
from agt.util import subprocess_run_and_log

try:
    from gi.repository import GObject
except ImportError:
    import gobject as GObject

# When gadget advertises for OOBE, set service data identifier
# https://developer.amazon.com/docs/alexa-gadgets-toolkit/bluetooth-le-settings.html#adv-packet-for-pairing
BLE_ADV_DATA_PAIR_CMD = 'sudo hcitool -i hci0 cmd 0x08 0x0008 ' \
                   ' 0x1F 0x02 0x01 0x06' \
                   ' 0x03 0x03 0x03 0xFE' \
                   ' 0x17 0x16 0x03 0xFE 0x71 0x01 0x00 0xFF ' \
                   '0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00'

# Skip the Service Data Identifier for reconnection
# https://developer.amazon.com/docs/alexa-gadgets-toolkit/bluetooth-le-settings.html#adv-packet-for-reconnection
BLE_ADV_DATA_RECONNECT_CMD = 'sudo hcitool -i hci0 cmd 0x08 0x0008 ' \
                             ' 0x1F 0x02 0x01 0x06' \
                             ' 0x1B 0x16 0x03 0xFE 0x71 0x01 0x00 0xFF' \
                             ' 0x00 0x00 0x00 0x00' \
                             ' 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00'

# Adv Params changed to 0x0020 (20 ms (32*0.625))
BLE_ADV_PARAMS_CMD = 'sudo hcitool -i hci0 cmd 0x08 0x0006 ' \
                     '0x20 0x00 0x20 0x00 ' \
                     '0x00 ' \
                     '0x00 ' \
                     '0x00 ' \
                     '0x00 0x00 0x00 0x00 0x00 0x00 ' \
                     '0x07 ' \
                     '0x00 '

BLE_ADV_DISABLE = 'sudo hcitool -i hci0 cmd 0x08 0x000a 00'
BLE_ADV_ENABLE = 'sudo hcitool -i hci0 cmd 0x08 0x000a 01'

GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
GATT_SERVICE_IFACE = 'org.bluez.GattService1'
GATT_CHRC_IFACE = 'org.bluez.GattCharacteristic1'
GATT_DESC_IFACE = 'org.bluez.GattDescriptor1'
DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'

logger = logging.getLogger(__name__)

class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.bluez.Error.NotSupported'

def _hciconfig(args):
    return subprocess.run(['/usr/bin/sudo', '/bin/hciconfig'] + args, stdout=subprocess.PIPE)

"""
BluetoothLEAdapter bluetooth interface for Alexa Gadgets application
"""
class BluetoothLEAdapter(dbus.service.Object):
    def __init__(self,
                 gadget_endpoint_id,
                 gadget_friendly_name,
                 gadget_device_type,
                 gadget_vendor_id,
                 gadget_product_id,
                 data_received_cb,
                 on_connection_cb,
                 on_disconnection_cb):
        self._protocol = BLEProtocol(gadget_endpoint_id, gadget_friendly_name, gadget_device_type,
                                                      data_received_cb, self.on_ready_to_send_data_cb)
        self._gatt_server = BLEGattTransport(self._protocol, gadget_friendly_name,
                                             on_connection_cb, on_disconnection_cb)
        self._gadget_friendly_name = gadget_friendly_name
        self._gadget_vendor_id = gadget_vendor_id
        self._gadget_product_id = gadget_product_id

    def start_server(self):
        """
        Start the server

        """
        # Main program calls a run after start_server; hence start_server does not need an implementation for BLE
        pass

    def stop_server(self):
        """
        Stop the server

        """
        self._gatt_server.stop()

    def poll_server(self):
        pass
    def send(self, data):
        """
        Send data

        :param data: Data to append
        """
        self._protocol.send_data(data)
    def on_ready_to_send_data_cb(self, payload):
        """
        Callback function when packetized data is ready to be sent over transport channel
        :return:
        """
        logger.debug('Sending packetized data')
        self._gatt_server.send_data(bytearray(payload))
    def set_discoverable(self, discoverable):
        if discoverable:
            self._gatt_server.set_advertisement_data(self._gadget_friendly_name, BLE_ADV_DATA_PAIR_CMD)
        self._gatt_server.toggle_advertisement(discoverable)
    def disconnect(self):
        """
        Disconnect the gadget

        """
        self._gatt_server.disconnect()
    def is_connected(self):
        return self._gatt_server.is_connected()
    def get_connection_info(self):
        raise NotSupportedException()
    def reconnect(self, bd_addr):
        self._gatt_server.set_advertisement_data(self._gadget_friendly_name, BLE_ADV_DATA_RECONNECT_CMD)
        self._gatt_server.toggle_advertisement(True)
    def is_paired_to_address(self, bd_addr):
        return self._gatt_server.is_paired_to_address(bd_addr)
    def unpair(self, bd_addr):
        self._gatt_server.unpair(bd_addr)
    def run(self):
        self._gatt_server.run()
    @staticmethod
    def get_address():
        """
        Gets the BD Address of the host

        :return: Host BD Address
        """
        p = _hciconfig(['hci0'])
        bdaddr = p.stdout.decode('utf-8').split('BD Address: ')[1].split(' ')[0]
        bdaddr = bdaddr.replace(':', '').strip()
        return bdaddr

"""
Application:
This class abstracts Bluez implementation for Gatt
application. It contains APIs for adding GadgetService
which further add the GATT characteristics for communication
between gadget and AlexaDevice
"""


class Application(dbus.service.Object):
    """
    org.bluez.GattApplication1 interface implementation
    """
    def __init__(self, bus, protocol):
        self._path = '/'
        self._protocol = protocol
        self._services = []
        dbus.service.Object.__init__(self, bus, self._path)
        self._gadgetService = AlexaGadgetService(bus, 0, self._protocol)
        self._add_service(self._gadgetService)

    def get_gadget_service(self):
        return self._gadgetService

    def get_path(self):
        return dbus.ObjectPath(self._path)

    def _add_service(self, service):
        self._services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        logger.debug('GetManagedObjects')

        for service in self._services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
                descs = chrc.get_descriptors()
                for desc in descs:
                    response[desc.get_path()] = desc.get_properties()

        return response


class Service(dbus.service.Object):
    """
    org.bluez.GattService1 interface implementation
    """
    PATH_BASE = '/org/bluez/example/service'

    def __init__(self, bus, index, uuid, primary):
        self._path = self.PATH_BASE + str(index)
        self._bus = bus
        self._uuid = uuid
        self._primary = primary
        self._characteristics = []
        dbus.service.Object.__init__(self, bus, self._path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': self._uuid,
                'Primary': self._primary,
                'Characteristics': dbus.Array(
                    self.get_characteristic_paths(),
                    signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self._path)

    def _add_characteristic(self, characteristic):
        self._characteristics.append(characteristic)

    def get_characteristic_paths(self):
        result = []
        for chrc in self._characteristics:
            result.append(chrc.get_path())
        return result

    def get_characteristics(self):
        return self._characteristics

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_SERVICE_IFACE]


class Characteristic(dbus.service.Object):
    """
    org.bluez.GattCharacteristic1 interface implementation
    """
    def __init__(self, bus, index, uuid, flags, service):
        self._path = service._path + '/char' + str(index)
        self._bus = bus
        self._uuid = uuid
        self._service = service
        self._flags = flags
        self._descriptors = []
        dbus.service.Object.__init__(self, bus, self._path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                'Service': self._service.get_path(),
                'UUID': self._uuid,
                'Flags': self._flags,
                'Descriptors': dbus.Array(
                    self.get_descriptor_paths(),
                    signature='o')
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self._path)

    def add_descriptor(self, descriptor):
        self._descriptors.append(descriptor)

    def get_descriptor_paths(self):
        result = []
        for desc in self._descriptors:
            result.append(desc.get_path())
        return result

    def get_descriptors(self):
        return self._descriptors

    @dbus.service.method(DBUS_PROP_IFACE,
                         in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE,
                         in_signature='a{sv}',
                         out_signature='ay')
    def ReadValue(self, options):
        logger.debug('Default ReadValue called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        logger.debug('Default WriteValue called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        logger.debug('Default StartNotify called, returning error')
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        logger.debug('Default StopNotify called, returning error')
        raise NotSupportedException()

    @dbus.service.signal(DBUS_PROP_IFACE,
                         signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

class AlexaGadgetService(Service):
    """
    AlexaGadget Gatt service

    """
    GADGET_UUID = '0000FE03-0000-1000-8000-00805F9B34FB'

    def __init__(self, bus, index, protocol):
        Service.__init__(self, bus, index, self.GADGET_UUID, True)

        self._protocol = protocol
        self._txChar = DataWriteCharacteristic(bus, 0, self, self._protocol)
        self._rxChar = DataReadCharacteristic(bus, 1, self, self._protocol)

        self._add_characteristic(self._txChar)
        self._add_characteristic(self._rxChar)

    def getTxChar(self):
        return self._txChar

    def getRxChar(self):
        return self._rxChar


class DataWriteCharacteristic(Characteristic):
    TX_UUID = 'F04EB177-3005-43A7-AC61-A390DDF83076'

    def __init__(self, bus, index, service, protocol):
        self._protocol = protocol
        Characteristic.__init__(
            self, bus, index,
            self.TX_UUID,
            ['encrypt-write'],
            service)

    def WriteValue(self, value, options):
        self._protocol.data_received(bytearray(value))


class DataReadCharacteristic(Characteristic):
    RX_UUID = '2BEEA05B-1879-4BB4-8A2F-72641F82420B'

    def __init__(self, bus, index, service, protocol):
        self._protocol = protocol
        Characteristic.__init__(
            self, bus, index,
            self.RX_UUID,
            ['encrypt-read', 'notify'],
            service)
        self._notifying = False

    def ReadValue(self, options):
        logger.debug('Rx value read: ' + repr(self._rx_value))
        return [dbus.Byte(self._rx_value)]

    # Call this method when you need to send data from the gadget
    def notify_rx_value(self, payload):
        if not self._notifying:
            logger.debug('notifications not enabled yet')
            return
        self.PropertiesChanged(
            GATT_CHRC_IFACE,
            {'Value': convert_to_dbus_array(payload)}, [])

    def StartNotify(self):
        logger.debug('notifications enabled')
        self._notifying = True
        time.sleep(1)
        self._protocol.gadget_ready()

    def StopNotify(self):
        logger.debug('notifications disabled')
        if not self._notifying:
            logger.debug('Not notifying, nothing to do')
            return
        self._notifying = False


def convert_to_dbus_array(payload):
    payload = bytearray(payload)
    out = []
    for b in payload:
        out = out + [dbus.Byte(b)]

    return dbus.Array(out, signature=dbus.Signature('y'))


def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BUS_NAME, '/'),
                               DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()
    for o, props in objects.items():
        if GATT_MANAGER_IFACE in props.keys():
            return o
    return None


def get_scan_resp_data(name):
    name_bytes = name.encode()
    namehex = codecs.encode(name_bytes, 'hex')
    str_hex_name = str(namehex, 'ascii')
    name_byte_list = ['0x' + str_hex_name[i:i+2] for i in range(0, len(str_hex_name), 2)]
    space_sep_name_hex = " ".join(name_byte_list)

    len_name = len(name_byte_list)
    len_with_flag = 1 + len_name # additional 1 for the type flag
    scan_resp_len = 1 + len_with_flag

    zeros = [0] * (31 - scan_resp_len)
    zero_list_str = " ".join(['0x{:02x}'.format(zeros[i]) for i in range(0, len(zeros), 1)])

    scan_resp = 'sudo hcitool -i hci0 cmd 0x08 0x0009 ' + '0x{:02x}'.format(scan_resp_len) + ' ' + '0x{:02x}'.format(len_with_flag) + ' 0x09 ' + space_sep_name_hex + ' ' + zero_list_str
    return scan_resp


"""
BLEGattTransport:
This class is the Transport level abstraction of BLE.
main creates and instance of this class which creates the Gatt
application with GATT service as described in the specification:
APP GATT Service:	0000FE03-0000-1000-8000-00805F9B34FB

APP Characteristic Tx:	F04EB177-3005-43A7-AC61-A390DDF83076	

APP Characteristic Rx:	2BEEA05B-1879-4BB4-8A2F-72641F82420B
"""


class BLEGattTransport(BaseAdapter):
    def __init__(self, protocol, gadget_name, on_connection_cb, on_disconnection_cb):
        logger.debug('resetting Bluez...')
        self.restart_bluez_deamon()
        logger.debug('Initializing BLE service')
        # protocol <-> Transport exchange packets for send/receive functionality
        # Initialize protocol object
        self._protocol = protocol
        self._is_connected = False
        self._gadget_name = gadget_name
        self._on_connect_cb = on_connection_cb
        self._on_disconnect_cb = on_disconnection_cb

        global mainloop
        DBusGMainLoop(set_as_default=True)
        dbus_loop = DBusGMainLoop()
        self._bus = dbus.SystemBus(dbus_loop)
        super().__init__(self._bus, dbus)

        self._adapter = find_adapter(self._bus)
        if not self._adapter:
            logger.debug('GattManager1 interface not found')
            return

        self._service_manager = dbus.Interface(
            self._bus.get_object(BUS_NAME, self._adapter),
            GATT_MANAGER_IFACE)

        self._application = Application(self._bus, self._protocol)
        self._loop = GObject.MainLoop()

        logger.debug('Registering GATT application...')
        self._service_manager.RegisterApplication(self._application.get_path(), {},
                                                  reply_handler=self.register_app_cb,
                                                  error_handler=self.register_app_error_cb)
        self.listen_properties_changed(self._bus)
        self.listen_interface_added(self._bus)

    def run(self):
        try:
            self._loop.run()
        except KeyboardInterrupt:
            logger.debug('mainloop interrupted')

    def restart_bluez_deamon(self):
        subprocess_run_and_log("systemctl daemon-reload")
        subprocess_run_and_log("systemctl restart bluetooth")

    def connect(self):
        self.set_advertisement_data(self._gadget_name, BLE_ADV_DATA_RECONNECT_CMD)
        self.toggle_advertisement(True)

    def is_connected(self):
        return self._is_connected

    def disconnect(self):
        logger.debug('ble: disconnect')
        cmd = 'echo "disconnect" | bluetoothctl'
        subprocess_run_and_log(cmd)

    def stop(self):
        # Make sure that the disconnect completes
        # before un registering the services.
        # Else it will cause EFD to be alerted of un-intended service
        # service removal, causing the gadget to be unusable
        logger.debug('quitting dbus mainloop')
        self.disconnect()
        logger.info('Disconnecting. Please wait for 5 seconds...')
        time.sleep(3)
        self._loop.quit()
        self._service_manager.UnregisterApplication(self._application)
        # sleep again to allow time for the application un-registration
        time.sleep(2)

    def send_data(self, payload):
        logger.debug('Sending payload, size=' + str(len(payload)))
        self._application._gadgetService._rxChar.notify_rx_value(payload)

    def register_app_cb(self):
        logger.debug('GATT application registered')

    def register_app_error_cb(self, error):
        logger.debug('Failed to register application: ' + str(error))
        self._loop.quit()

    def set_advertisement_data(self, name, cmd):
        logger.debug('set_advertisement')
        try:
            subprocess_run_and_log('sudo hciconfig hci0 up')
            subprocess_run_and_log(cmd)

            subprocess_run_and_log(get_scan_resp_data(name))
        except Exception as e:
            logger.error(e)

    def toggle_advertisement(self, enable):
        try:
            if enable is False:
                subprocess_run_and_log(BLE_ADV_DISABLE)
            else:
                subprocess_run_and_log(BLE_ADV_PARAMS_CMD)
                time.sleep(1)
                subprocess_run_and_log(BLE_ADV_ENABLE)
        except Exception as e:
            logger.error(e)

    def listen_properties_changed(self, bus):
        bus.add_signal_receiver(self.property_changed, bus_name="org.bluez",
                                dbus_interface="org.freedesktop.DBus.Properties",
                                signal_name="PropertiesChanged",
                                path_keyword="path")

    def listen_interface_added(self, bus):
        bus.add_signal_receiver(self.interface_added,
                                dbus_interface="org.freedesktop.DBus.ObjectManager",
                                signal_name="InterfaceAdded")

    def interface_added(self, path, interfaces):
        logger.debug('interface_changed')

    def property_changed(self, interface, changed, invalidated, path):
        iface = interface[interface.rfind(".") + 1:]
        for name, value in changed.items():
            val = str(value)
            logger.debug("{%s.PropertyChanged} [%s] %s = %s" % (iface, path, name,
                                                         val))
            logger.debug(str(name))
            logger.debug(str(val))
            if str(name) == 'Connected' and str(val) == '1':
                logger.debug('device connected. Disabling advertisement')
                mac_address = get_address_from_path(path)
                self.toggle_advertisement(False)
                self._on_connect_cb(mac_address)
                self._is_connected = True
            elif str(name) == 'Connected' and str(val) == '0':
                logger.debug('device is disconnected.')
                self._application._gadgetService._rxChar.StopNotify()
                self._on_disconnect_cb(get_address_from_path(path))
                self._is_connected = False
                self.connect()

    def unpair(self, bd_addr):
        super(BLEGattTransport, self).unpair(bd_addr)

    def is_paired_to_address(self, bd_addr):
        return super(BLEGattTransport, self).is_paired_to_address(bd_addr)

def get_address_from_path(path):
    addr_path = path.split('/')
    addr_path = addr_path[len(addr_path) - 1]
    literals = addr_path.split('_')
    bdaddr = ':'.join(i for i in literals[1:])
    return bdaddr
