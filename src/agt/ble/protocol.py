#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#
import dbus
import logging.config
from agt.ble.messages_pb2 import ControlEnvelope
from agt.ble.messages_pb2 import GET_DEVICE_INFORMATION, GET_DEVICE_FEATURES, NONE, BLUETOOTH_LOW_ENERGY
from agt.util import log_bytes


class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = 'org.bluez.Error.NotSupported'


logger = logging.getLogger(__name__)

"""
BLE Streams ID
https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header

0000: Control stream
0110: Alexa stream
0010: OTA stream - Not supported currently
"""
class AppStreams:
    ALEXA_STREAM_ID = 6
    CONTROL_STREAM_ID = 0
    OTA_STREAM_ID = 2
"""
Transaction Type
https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header
  		  
Offset=12, Length=2
"""
class TransactionType:
    FIRST_PACKET = 0
    CONTINUATION_PACKET = 1
    LAST_PACKET = 2
    CONTROL_PACKET = 3

"""
Protocol Version Packet
https://developer.amazon.com/docs/alexa-gadgets-toolkit/bluetooth-le-settings.html#pvp
Gadget Developers can choose the appropriate values for these, please refer to the developer documentation.
"""
PROTOCOL_VERSION_PACKET_PREFIX = [0xfe, 0x03,  # 2 bytes for Protocol identifier 0XFE03
                                  0x03,  # 1 byte Major Version
                                  0x00]  # 1 byte Minor Version
MTU_SIZE = [0x02, 0x00]  # 2 bytes MTU Size
MAX_TRANSACTIONAL_SIZE = [0x13, 0x88]  # Max Transactional Data Size
# 12 bytes Reserved
PROTOCOL_VERSION_PACKET_SUFFIX = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

""""
BLE Protocol implements the Bluetooth Low Energy protocol for Alexa Gadgets
as defined here:
https://developer.amazon.com/docs/alexa-gadgets-toolkit/bluetooth-le-pair-connect.html
This class is responsible for the communication between the transport and the gadget
It is also responsible for performing the protocol specific control message exchanges between
the gadget and the Alexa Device
"""


class BLEProtocol:
    def __init__(self, endpoint_id, friendly_name, amazon_device_type, data_received_cb, on_data_ready_cb):
        self._packetizer = Packetizer(MTU_SIZE)
        self.control_stream_parser = ControlMessageParser(endpoint_id, friendly_name, amazon_device_type)
        self._data_received_cb = data_received_cb
        self._on_data_ready_cb = on_data_ready_cb

    def data_received(self, payload):
        data, stream_id, ack, tx_id = self._packetizer.deserialize(bytearray(payload))
        if data is not None:
            logger.debug("===========StreamID:%d==========" % stream_id)
            if int(stream_id) == AppStreams.CONTROL_STREAM_ID:
                control_msg_resp, parsed_input = self.control_stream_parser.parse_payload(bytearray(data))
                if control_msg_resp is not None:
                    log_bytes(control_msg_resp)
                    self.send_data(control_msg_resp, AppStreams.CONTROL_STREAM_ID)
            elif int(stream_id) == AppStreams.ALEXA_STREAM_ID:
                self._data_received_cb(data)
            self.send_transport_ack(stream_id, ack, tx_id)

    def send_transport_ack(self, stream_id, ack, tx_id):
            if int(ack) == 1:
                logger.debug('sending Transport ack')
                sequences = self._packetizer.create_ack_message(int(ack), stream_id, tx_id)
                self._on_data_ready_cb(sequences)

    def send_data(self, message, stream_id=AppStreams.ALEXA_STREAM_ID):
        if message is not None:
            sequences = self._packetizer.serialize(message, stream_id)
            logger.debug('total sequences to be sent:' + str(len(sequences)))
            for sequence in sequences:
                self._on_data_ready_cb(sequence)

    """
    Handshake data that needs to be sent by the gadget as soon as connection has been
    established with the Echo device
    https://developer.amazon.com/docs/alexa-gadgets-toolkit/bluetooth-le-settings.html
    """

    def gadget_ready(self):
        logger.debug('gadget ready, sending protocol version update')
        protocol_version_packet = PROTOCOL_VERSION_PACKET_PREFIX + MTU_SIZE + MAX_TRANSACTIONAL_SIZE + PROTOCOL_VERSION_PACKET_SUFFIX
        log_bytes(protocol_version_packet)
        self._on_data_ready_cb(protocol_version_packet)

"""
ControlMessageParser
This class is responsible for parsing the control messages sent
by the Echo Device, and responding with the Control messages
such as Ack, query response, feature response etc.
"""

class ControlMessageParser:
    def __init__(self, serial_number, name, device_type):
        logger.debug('message parser object instantiated')
        self.serial_number = serial_number
        self.name = name
        self.device_type = device_type

    def parse_payload(self, payload):
        try:
            msg_parser = ControlEnvelope()
            msg_parser.ParseFromString((bytes(payload)))

            if GET_DEVICE_INFORMATION == msg_parser.command:
                logger.debug("====== Device Info Query ======")
                return self._create_device_info_response(), msg_parser
            elif GET_DEVICE_FEATURES == msg_parser.command:
                logger.debug('======= Feature Query ======')
                return self._create_feature_query_response(), msg_parser
            else:
                logger.debug('CommandID:' + str(msg_parser.command))

        except Exception as e:
            logger.error('exception:' + str(e.message))

    def _create_feature_query_response(self):
        ## https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#device-features-response
        try:
            msg_creator = ControlEnvelope()
            msg_creator.command = GET_DEVICE_FEATURES
            # Offset 0=AGT
            msg_creator.response.device_features.features = 0x01
            msg_creator.response.device_features.device_attributes = 0
            serial_val = msg_creator.SerializeToString()
            return serial_val
        except Exception as e:
            logger.error(e)

    def _create_device_info_response(self):
        ## https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#device-information-response
        try:
            msg_creator = ControlEnvelope()
            msg_creator.command = GET_DEVICE_INFORMATION
            msg_creator.response.device_information.serial_number = self.serial_number
            msg_creator.response.device_information.name = self.name
            msg_creator.response.device_information.supported_transports.extend([BLUETOOTH_LOW_ENERGY])
            msg_creator.response.device_information.device_type = self.device_type
            serial_val = msg_creator.SerializeToString()
            return serial_val
        except Exception as e:
            logger.error('exception:' + str(e))

class Packetizer:
    def __init__(self, max_payload_size):
        self.max_payload_size = int.from_bytes(max_payload_size, byteorder='big')
        # Rx params
        self.pending_read = {}
        self.init_streams()

        # Tx params
        self.transaction_id = 0

    def init_streams(self):
        self.pending_read = {
            str(AppStreams.CONTROL_STREAM_ID): bytearray(),
            str(AppStreams.ALEXA_STREAM_ID): bytearray(),
        }

    """
    https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header
    |
    |STREAM_ID|TRANSACTION_ID|SEQ_NO|TX TYPE|ACK(1)/NACK(0)|LengthExt|   RESERVED   |Length (=2)|MsgType (0x01)|ErrorCode|
    |----4----|------4-------|--4---|---2---|--------1-----|----1----|-------8------|------8----|------8-------|----8----|
    |--------Byte1-----------|------------Byte2----------------------|-----Byte3----|---Byte4---|-----Byte5----|--Byte6--|
    """
    def create_ack_message(self, ack, stream_id, tx_id):
        sequences = [None]
        sequence = bytearray()

        # Byte1: StreamID, Transaction ID
        sequence += bytes([((stream_id << 4) & 0xF0) | (tx_id & 0x0F)])
        seq_no = 0

        # Total Length of ack packet 1 byte ACK/NACK, 2nd byte is Error Code
        total_length = 2

        # Byte2: SeqNo, Transaction Type(11), reserved, length extender (0)
        byte2 = (seq_no << 4) & 0xF0
        tx_type = TransactionType.CONTROL_PACKET
        byte2 = byte2 | ((tx_type << 2) & 0x0C)  # Control message

        # ACK bit
        if ack:
            byte2 = byte2 | (0x01 << 1)

        sequence += bytes([byte2])

        # if first packet add an empty byte (Reserved)
        sequence += bytes([0x00])

        # total transaction len (8 bits)
        sequence += bytes([total_length & 0xFF])

        byte5 = 0x01  # 0x01 for ACK/NACK
        sequence += bytes([byte5 & 0xFF])

        # Error Code
        sequence += bytes([0x00])
        sequences[seq_no] = sequence
        return sequences

    """
    https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header
    |
    |STREAM_ID|TRANSACTION_ID|SEQ_NO|TX TYPE|ACK(1)/NACK(0)|LengthExt|   RESERVED   |Length (=2)|MsgType (0x01)|ErrorCode|
    |----4----|------4-------|--4---|---2---|--------1-----|----1----|-------8------|------8----|------8-------|----8----|
    |--------Byte1-----------|------------Byte2----------------------|-----Byte3----|---Byte4---|-----Byte5----|--Byte6--|
    """
    def serialize(self, payload, stream_id):
        if not payload:
            logger.info("Empty payload received")
            return
        payload = bytearray(payload)

        total_length = len(payload)
        """
        # First packets have a 6 byte header by default; 7 if length extender is used,
        # Continuation packets have a 3 byte header ; 4 if length extender is used whereas
        # Last packet have a 3 byte header; 4 if length extender is used.
        # Using the max header size so that payload fits within MTU
        https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header
        """
        mtu = self.max_payload_size - 7
        if mtu is 0:
            raise Exception('MTU value cannot be 0')

        total_sequences = int(total_length/mtu + (1 if total_length%mtu != 0 else 0))

        sequences = [None] * total_sequences
        # start index
        si = 0
        # end index
        ei = mtu if mtu < (total_length - si) else (total_length - si)
        seq_no = 0

        while si != ei:
            sequence = bytearray()
            sequence += bytes([((stream_id << 4) & 0xF0) | (self.transaction_id & 0x0F)])

            # byte 2.
            byte2 = (seq_no << 4) & 0xF0

            if seq_no == 0:
                tx_type = TransactionType.FIRST_PACKET
            elif seq_no == total_sequences - 1:
                tx_type = TransactionType.LAST_PACKET
            else:
                tx_type = TransactionType.CONTINUATION_PACKET
            byte2 = byte2 | ((tx_type << 2) & 0x0C)
            payload_length = ei - si
            """
            Length extender
            ## https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header
            # Offset 15
            0: The packet's payload is 8 bits.
            1: The packet's payload is 16 bits.
            """
            length_extension = False
            if payload_length > 255:
                byte2 = byte2 | 0x01
                length_extension = True

            sequence += bytes([byte2])

            # if first packet add an empty byte (Reserved)
            if tx_type == TransactionType.FIRST_PACKET:
                sequence += bytes([0x00])

                # total transaction len (16 bits)
                sequence += bytes([(total_length >> 8) & 0xFF])
                sequence += bytes([total_length & 0xFF])

            if length_extension:
                sequence += bytes([(payload_length >> 8) & 0xFF])
            sequence += bytes([payload_length & 0xFF])
            # finally add the payload
            sequence = sequence + bytearray(payload[si:ei])
            sequences[seq_no] = sequence
            seq_no += 1

            si = ei
            ei = (mtu if mtu < (total_length - si) else (total_length - si)) + si

        self.transaction_id += 1
        return sequences


    """
    https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header
    |
    |STREAM_ID|TRANSACTION_ID|SEQ_NO|TX TYPE|ACK(1)/NACK(0)|LengthExt|   RESERVED   |Length (=2)|MsgType (0x01)|ErrorCode|
    |----4----|------4-------|--4---|---2---|--------1-----|----1----|-------8------|------8----|------8-------|----8----|
    |--------Byte1-----------|------------Byte2----------------------|-----Byte3----|---Byte4---|-----Byte5----|--Byte6--|
    
    """
    def deserialize(self, payload):
        count = 0
        if not payload:
            logger.info("Empty payload received")
            return
        payload = bytearray(payload)
        stream_id, tx_id = self.parse_first_byte(payload[count])
        count += 1

        seq_no, tx_type, le, ack = self.parse_second_byte(payload[count])
        count += 1

        # handle length extender separately

        if tx_type == TransactionType.FIRST_PACKET:
            # skip the reserved byte
            count += 1
            # this is present only in first packet
            total_length = (payload[count] << 8) + payload[count+1]
            count += 2

        # get the length of current payload
        if str(le) == '1':
            tx_length = (payload[count] << 8) + payload[count+1]
            count += 2
        else:
            tx_length = payload[count]
            count += 1

        binary_payload = payload[count:count+tx_length]

        # first packet and no more packets
        if tx_type == TransactionType.FIRST_PACKET and tx_length == total_length:
            # first and only packet. Pass to the application
            return binary_payload, stream_id, ack, tx_id
        elif tx_type == TransactionType.FIRST_PACKET or tx_type == TransactionType.CONTINUATION_PACKET:
            # first packet, but not the last
            self.pending_read[str(stream_id)] = self.pending_read[str(stream_id)] + binary_payload
            return None, None, None, None
        elif tx_type == TransactionType.LAST_PACKET:
            # Last packet. Send the complete packet to app
            ret_arr = self.pending_read[str(stream_id)] + binary_payload
            self.pending_read[str(stream_id)] = bytearray()
            return ret_arr, stream_id, ack, tx_id

    """
    Parse first byte of the header
    https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header
    |
    |STREAM_ID|TRANSACTION_ID|
    |----4----|------4-------|
    |--------Byte1-----------|
    """
    def parse_first_byte(self, val):
        stream_id = val >> 4
        tx_id = val & 0x0F
        return stream_id, tx_id

    """
    Parse second byte of the header
    https://developer.amazon.com/docs/alexa-gadgets-toolkit/packet-ble.html#header
    |
    |SEQ_NO|TX TYPE|ACK(1)/NACK(0)|LengthExt|
    |--4---|---2---|--------1-----|----1----|
    |------------Byte2----------------------|
    """
    def parse_second_byte(self, val):
        seq_no = val >> 4

        nibble2 = val & 0x0F
        tx_type = nibble2 >> 2

        lextender = nibble2 & 0x01
        ack = (nibble2 >> 1) & 0x01
        return seq_no, tx_type, lextender, ack