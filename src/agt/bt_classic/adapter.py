#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

import binascii
import dbus
import dbus.service
import logging.config
import select
import subprocess
import threading
import uuid
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GObject
from agt.base_adapter import BaseAdapter
from agt.base_adapter import BUS_NAME, ADAPTER_INTERFACE, DBUS_OM_IFACE, DEVICE_INTERFACE
import bluetooth

logger = logging.getLogger(__name__)

"""
Constants
"""
_STX = 0xF0  # Start transmission
_ETX = 0xF1  # End transmission.
_ESC = 0xF2  # Escape character to allow reserved characters.

_RESERVED = [_STX, _ETX, _ESC]

# Indicate no error.
_ERR = 0x00
# Hardcoded per documentation.
_CMD = 0x02

_SPP_CHANNEL = 4

"""
BlueZ constants
"""
BLUEZ_AGENT_PATH = '/org/bluez/agent'
AGENT_INTERFACE = 'org.bluez.Agent1'
AGENT_MANAGER_INTERFACE = 'org.bluez.AgentManager1'
PROFILE_MANAGER_INTERFACE = 'org.bluez.ProfileManager1'
DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'

IO_CAPABILITY = 'NoInputNoOutput'

def _hciconfig(args):
    return subprocess.run(['/usr/bin/sudo', '/bin/hciconfig'] + args, stdout=subprocess.PIPE)


def _sdptool(args):
    return subprocess.run(['/usr/bin/sudo', '/usr/bin/sdptool'] + args, stdout=subprocess.PIPE)

"""
BluetoothAdapter bluetooth interface for Alexa Gadgets application
"""
class BluetoothAdapter(dbus.service.Object):

    def __init__(self,
                 gadget_friendly_name,
                 gadget_vendor_id,
                 gadget_product_id,
                 spp_data_handler_cb,
                 on_connection_cb,
                 on_disconnection_cb):
        # initialize BlueZAPI
        self._bluez_api = _BlueZAPI()

        """
        Create connections.

        :param _SPP_CHANNEL: port number for RFCOMM
        :param spp_data_handler_cb: Callback for raw spp data.
        :param on_connection_cb: Callback when connection is up
        :param on_disconnection_cb: Callback when connection is down
        """
        # initialize RFCOMM server
        self._spp_server = _RFCOMMServer(_SPP_CHANNEL, spp_data_handler_cb, on_connection_cb, on_disconnection_cb)

        self._gadget_friendly_name = gadget_friendly_name
        self._gadget_vendor_id = gadget_vendor_id
        self._gadget_product_id = gadget_product_id

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

    def start_server(self):
        """
        Start the connection, registering as a gadget.

        """
        _create_service_records()
        self._spp_server.start()

    def stop_server(self):
        """
        Stop the server

        """
        self.disconnect()
        self._bluez_api.stop_dbus()

    def poll_server(self):
        """
        Check the servers for connection/data.

        """
        self._spp_server.poll()

    def send(self, data):
        """
        Send data to a server.

        :param data:

        """
        # Generate SPP packet before sending over SPP server
        packet = _SPPPacket()
        packet.payload = data
        self._spp_server.send(packet.get())

    def set_discoverable(self, discoverable):
        """
        Turn on/off discoverability.

        :param discoverable: On/Off for discoverable.
        """
        if discoverable:
            self._bluez_api.start_inbound_pairing_mode(self._gadget_friendly_name, self._create_eir())
        else:
            self._bluez_api.stop_inbound_pairing_mode()

    def disconnect(self):
        self._spp_server.disconnect()

    def is_connected(self):
        """
        Report whether connection is active.

        :return: Boolean whether connection is active.
        """
        return self._spp_server.is_connected()

    def get_connection_info(self):
        return self._spp_server.get_connection_info()

    def reconnect(self, bdaddr):
        """
        Reconnect to a bdaddr specified by bdaddr.

        :param bdaddr: Address to reconnect to.
        """
        _sdptool(['search', '--bdaddr', bdaddr, '0x1101'])

    def is_paired_to_address(self, bd_addr):
        return self._bluez_api.is_paired_to_address(bd_addr)

    def unpair(self, bd_addr):
        self._bluez_api.unpair(bd_addr)

    def run(self):
        self._bluez_api.run_dbus()

    def _create_eir(self):
        """
        Create extended inquiry response.

        """
        # Length, address, and actual name
        eir = '{0:0{1}x}'.format(1 + len(self._gadget_friendly_name), 2)
        eir += '09'
        eir += binascii.hexlify(self._gadget_friendly_name.encode('utf8')).decode('utf-8')

        # Length, address, and actual UUID
        eir += '11'
        # Address for UUID data,
        eir += '06'
        eir += 'B7166825D15A949FED4E3A98B3D28860'

        # Length, address, and actual manufacturer data.
        eir += '0b'
        eir += 'ff'
        # Vendor ID, Product ID, Amazon SIG VID, Amazon Gadget UUID
        eir += self._gadget_vendor_id
        eir += self._gadget_product_id

        eir += '7101'
        eir += '101515fe'

        # End of data
        eir += '00'

        return eir


class _RFCOMMServer:
    """
    RFCOMM server using pybluez
    """

    def __init__(self, channel, data_handler_cb, on_connected_cb, on_disconnected_cb):
        """
        Initializer a single server.

        :param channel: Channel to connect.
        :param data_handler_cb: Data sink.
        :param on_connected_cb: Connection success.
        :param on_disconnected_cb: Disconnection.

        """
        self._data_handler_cb = data_handler_cb
        self._on_connected_cb = on_connected_cb
        self._on_disconnected_cb = on_disconnected_cb
        self._channel = channel

        self._server = bluetooth.BluetoothSocket(bluetooth.RFCOMM)

        self._socket = None
        self._info = None
        self._send_queue = bytearray()

        self._send_queue_available = threading.Condition()

        self._spp_parser = _Parser(self._data_handler_cb)

    def start(self):
        """
        Start the server.

        """
        self._server.bind(('', self._channel))
        self._server.listen(1)

    def send(self, data):
        """
        Send data, it is thread safe although there isn't any multi-threading.

        :param data: Data to append, None will clear queue.
        """
        self._send_queue_available.acquire()
        if data is None:
            self._send_queue = bytearray()
        elif self.is_connected():
            self._send_queue += data
        self._send_queue_available.release()

    def poll(self):
        """
        Check the server for a connection or data.

        """
        if self.is_connected():
            self._poll_read()
            self._poll_write()
        else:
            self._poll_connect()

    def is_connected(self):
        """
        Report whether server is connected.

        :return: True/False if server is connected.
        """
        return self._socket is not None

    def disconnect(self):
        """
        Close and disconnect socket.

        """
        if self._socket:
            prev_info = self._info
            self._socket.close()
            self._socket = None
            self._info = None
            self._on_disconnected_cb(prev_info[0])

    def get_connection_info(self):
        """
        Get information on the current connection.

        :return: A connection tuple of (address, channel) or (None, None) if not connected.
        """
        if self.is_connected():
            return self._info
        else:
            return None, None

    def _poll_connect(self):
        """
        Poll the server to see if a connection is accepted.

        """
        available, _, _ = select.select([self._server], [], [], 0)

        if len(available):
            self._connect()

    def _connect(self):
        self._socket, self._info = self._server.accept()
        self.send(None)
        self._on_connected_cb(self._info[0])

    def _poll_read(self):
        """
        Poll a connection to see if data is available or needs to be sent.

        """
        if self._socket is not None:
            readable, _, _ = select.select([self._socket], [], [], 0)

            if len(readable):
                self._read()

    def _read(self):
        data = bytes()
        try:
            data = self._socket.recv(1024)
        except bluetooth.btcommon.BluetoothError as e:
            # Indicates a broken connection.
            logger.debug('Bluetooth connection broken: {}'.format(e))
        finally:
            if len(data):
                self._spp_parser.parse(data)
            else:
                self.disconnect()

    def _poll_write(self):
        if self._socket is not None:
            _, writable, _ = select.select([], [self._socket], [], 0)

            if len(writable):
                self._write()

    def _write(self):
        count = 0
        try:
            self._send_queue_available.acquire()
            if len(self._send_queue):
                count = self._socket.send(bytes(self._send_queue))
        except bluetooth.btcommon.BluetoothError as e:
            # Indicates a broken connection.
            logger.debug('Bluetooth connection broken: {}'.format(e))
            self.disconnect()
        finally:
            self._send_queue = self._send_queue[count:]
            self._send_queue_available.release()


class _Parser:
    """
    The Parser class will handle the standard SPP packet.
    """

    def __init__(self, payload_cb):
        """
        Initialize

        :param payload_cb: Callback to send a completed payload.
        """
        self._payload_cb = payload_cb
        self._data = bytearray()
        self._state = self._state_find_stx
        self._packet = None

    def parse(self, data):
        """
        Parse incoming data, will call the payload cb when a packet is found.

        :param data: New data.
        """
        self._data += bytearray(data)
        while len(self._data):
            self._state(self._data.pop(0))

    def _start_packet(self):
        """
        Begin a new packet.

        """
        self._packet = _SPPPacket()
        self._state = self._state_get_command_id

    def _state_find_stx(self, c):
        """
        Find start transmission (STX) character.   Followed by state_get_command_id()

        :param c: Char to parse
        """
        if c == _STX:
            self._start_packet()

    def _state_get_command_id(self, c):
        """
        Accept command id character.   Followed by state_get_error_id().
        Will drop back to start if STX is found.

        :param c: Char to parse
        """
        if c == _STX:
            self._start_packet()
        else:
            self._packet.command_id = c
            self._state = self._state_get_error_id

    def _state_get_error_id(self, c):
        """
        Accept error id character.   Followed by state_get_seq_id().
        Will drop back to start if STX is found.

        :param c: Char to parse
        """
        if c == _STX:
            self._start_packet()
        else:
            self._packet.error_id = c
            self._state = self._state_get_seq_id

    def _state_get_seq_id(self, c):
        """
        Accept sequence id character.   Followed by state_get_data().
        Will drop back to start if STX is found.

        :param c: Char to parse
        """
        if c == _STX:
            self._start_packet()
        elif c == _ESC:
            self._state = self._state_get_seq_id_escaped
        else:
            self._packet.sequence_id = c
            self._state = self._state_get_data

    def _state_get_seq_id_escaped(self, c):
        """
        Accept a single escaped character (seq_id can also be escaped)

        :param c: Char to parse
        """

        self._packet.sequence_id = _ESC ^ c
        self._state = self._state_get_data

    def _state_get_data(self, c):
        """
        Accept payload.  This could be an escaped character (state_get_escaped()
        Will drop back to start if STX is found, and validate checksum and send payload if ETX is found.

        :param c: Char to parse
        """
        if c == _STX:
            self._start_packet()
        elif c == _ESC:
            self._state = self._state_get_escaped
        elif c == _ETX:
            # Last two bytes are checksum
            if len(self._packet.payload) >= 2:
                found_checksum = self._packet.payload.pop() + (self._packet.payload.pop() << 8)
                # Then get actual
                calc_checksum = self._packet._calc_checksum()

                if found_checksum == calc_checksum:
                    self._payload_cb(self._packet.payload)

            self._state = self._state_find_stx
        else:
            self._packet.payload.append(c)

    def _state_get_escaped(self, c):
        """
        Accept a single escaped character.

        :param c: Char to parse
        """
        self._packet.payload.append(_ESC ^ c)
        self._state = self._state_get_data


def _create_service_records():
    """
    Create BT service records.

    """
    _bus = dbus.SystemBus().get_object(BUS_NAME, '/org/bluez')
    _manager = dbus.Interface(_bus, PROFILE_MANAGER_INTERFACE)

    _opts = {
        'Role': 'server',
        'RequireAuthentication': False,
        'RequireAuthorization': False
    }

    def _create_record(path, xml_record):
        """
        Register a single BT service.

        """
        _opts['ServiceRecord'] = xml_record
        _manager.RegisterProfile(path, str(uuid.uuid4()), _opts)

    # Primary gadget record
    _create_record('/bluez5',
                   """
                   <?xml version="1.0" encoding="UTF-8" ?>
                   <record>
                       <attribute id="0x0001">
                           <sequence>
                               <uuid value="6088d2b3-983a-4eed-9f94-5ad1256816b7" />
                           </sequence>
                       </attribute>
                       <attribute id="0x0004">
                           <sequence>
                               <sequence>
                                   <uuid value="0x0100" />
                                   <uint16 value="0x0001" />
                               </sequence>
                               <sequence>
                                    <uuid value="0x0001" />
                               </sequence>
                           </sequence>
                       </attribute>
                       <attribute id="0x0100">
                           <text value="gadget" />
                       </attribute>
                   </record>
                   """)

    # This is for the two SPP channels
    def _create_channel_xml(uuid, channel):
        """
        Create XML string for a single record.

        :return: XML record
        """
        return """
            <?xml version="1.0" encoding="UTF-8" ?>
            <record>
            <!-- UUID -->
             <attribute id="0x0001">
                <sequence>
                    <uuid value="%s" />
                </sequence>
             </attribute>

             <!-- Protocols -->
             <attribute id="0x0004">
                <sequence>
                    <sequence>
                        <uuid value="0x0100" /> <!-- L2CAP -->
                    </sequence>
                    <sequence>
                        <uuid value="0x0003" /> <!-- RFCOMM -->
                        <uint8 value="0x0%d" /> <!-- Channel -->
                    </sequence>
                </sequence>
             </attribute>
             <!-- BrowseGroup -->
             <attribute id="0x0005">
                <sequence>
                    <uuid value="0x1002" /> <!-- PublicBrowseRoot -->
                </sequence>
             </attribute>
             <!-- Profile descriptors -->
             <attribute id="0x0009">
                <sequence>
                    <sequence>
                        <uuid value="%s" /> <!-- UUID -->
                        <uint16 value="0x0102" />
                    </sequence>
                </sequence>
             </attribute>
             <attribute id="0x0100">
                <text value="RFC SERVER" />
             </attribute>
            </record>
            """ % (uuid, channel, uuid)

    # Create primary service record
    _create_record('/bluez3', _create_channel_xml('0x1201', _SPP_CHANNEL))


class _SPPPacket:
    _SEQ_ID = 0

    def __init__(self):
        """
        Create SPP packet.
        """
        self.payload = bytearray()
        self.command_id = None
        self.error_id = None

    def get(self):
        """
        Create a full packet from payload.

        """
        header = self._get_header()
        self.command_id = _CMD
        self.error_id = _ERR
        checksum = self._calc_checksum()
        payload_to_escape = self.payload + bytearray([checksum >> 8, checksum & 0xFF])
        payload_escaped = bytearray()
        for b in payload_to_escape:
            if b in _RESERVED:
                payload_escaped.append(_ESC)
                payload_escaped.append(_ESC ^ b)
            else:
                payload_escaped.append(b)
        payload_escaped.append(_ETX)

        return header + payload_escaped

    def _calc_header_checksum(self):
        return self.command_id + self.error_id

    def _get_header(self):
        return bytearray([_STX, _CMD, _ERR, self._get_sequence_id()])

    def _calc_checksum(self):
        """
        Calculate the payload checksum.

        """
        payload_sum = sum(self.payload)
        checksum = payload_sum + self._calc_header_checksum()

        return checksum & 0xFFFF

    @staticmethod
    def _get_sequence_id():
        """
        Create a sequence id.

        :return: Sequence id.
        """
        retval = _SPPPacket._SEQ_ID

        while True:
            _SPPPacket._SEQ_ID += 1
            _SPPPacket._SEQ_ID &= 0xFF

            if _SPPPacket._SEQ_ID not in _RESERVED:
                break

        return retval

class _BlueZAPI(dbus.service.Object, BaseAdapter):
    """
    A python wrapper for BlueZ dbus APIs
    """

    def __init__(self):
        # sspmode (Simple Secure Pairing Mode) should always be 1.
        # 0 indicates the legacy pairing using pin code.
        _hciconfig(['hci0', 'sspmode', '1'])

        # initialize Mainloop
        DBusGMainLoop(set_as_default=True)

        # initialize agent interface
        self._loop = GObject.MainLoop()
        self._bus = dbus.SystemBus()
        dbus.service.Object.__init__(self, self._bus, BLUEZ_AGENT_PATH)
        BaseAdapter.__init__(self, self._bus, dbus)

        # initialize bluez properties
        self._bluez_properties = dbus.Interface(self._bus.get_object(BUS_NAME, self.bluez_adapter.object_path), DBUS_PROP_IFACE)

        # initialize bluez agent manager
        self._bluez_agent_manager = dbus.Interface(self._bus.get_object(BUS_NAME, '/org/bluez'), AGENT_MANAGER_INTERFACE)


    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        logger.debug("Authroize Service (%s, %s) of peer device" % (device, uuid))
        self._trustDevice(device)

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        logger.error("Error: wrong IO Capability used: DisplayPinCode: (%s, %s)" % (device, pincode))

    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        logger.error("Error: wrong IO Capability used: DisplayPasskey: (%s, %06u entered %u)" % (device, passkey, entered))

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        logger.error("Error: wrong IO Capability used: RequestPinCode: (%s)" % (device))
        return ""

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        logger.error("Error: wrong IO Capability used: RequestPasskey returns 0")
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        # Always confirm without asking
        logger.debug("RequestConfirmation (%s)" % (device))
        self._trustDevice(device)

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        # Always authorize without asking
        logger.debug("RequestAuthorization (%s)" % (device))

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self):
        logger.info("Canel Pairing")

    def run_dbus(self):
        self._loop.run()

    def stop_dbus(self):
        self._loop.quit()

    def _trustDevice(self, path):
        self._bluez_properties.Set(DEVICE_INTERFACE, "Trusted", True)

    def start_inbound_pairing_mode(self, friendly_name, eir):
        '''
        Start inbound pairing mode using friendly name and EIR.
        Inbound means this device is passively being paired by another device.
        '''

        # hci commands to configure EIR
        _hciconfig(['hci0', 'reset'])
        _hciconfig(['hci0', 'name', friendly_name])
        # mode 2 means inq with EIR
        _hciconfig(['hci0', 'inqmode', '2'])
        _hciconfig(['hci0', 'inqdata', eir])
        # piscan means both page scan and inquire scan
        _hciconfig(['hci0', 'piscan'])
        # btm commands to configure pairing mode
        self._bluez_agent_manager.RegisterAgent(BLUEZ_AGENT_PATH, IO_CAPABILITY)
        self._bluez_agent_manager.RequestDefaultAgent(BLUEZ_AGENT_PATH)
        self._bluez_properties.Set(ADAPTER_INTERFACE, 'Pairable', True)
        self._bluez_properties.Set(ADAPTER_INTERFACE, 'Discoverable', True)

    def stop_inbound_pairing_mode(self):
        self._bluez_properties.Set(ADAPTER_INTERFACE, 'Discoverable', False)
        self._bluez_properties.Set(ADAPTER_INTERFACE, 'Pairable', False)
        _hciconfig(['hci0', 'noscan'])

    def is_paired_to_address(self, bd_addr):
        return super(_BlueZAPI, self).is_paired_to_address(bd_addr)

    def unpair(self, bd_addr):
        super(_BlueZAPI, self).unpair(bd_addr)
