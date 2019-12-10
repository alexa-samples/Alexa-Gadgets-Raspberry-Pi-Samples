#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#


import argparse
import configparser
import hashlib
import json
import logging.config
import signal
import sys
import time
from os import path
from threading import Thread

from google.protobuf import json_format

import agt.messages_pb2 as proto
from agt.bt_classic.adapter import BluetoothAdapter
from agt.ble.adapter import BluetoothLEAdapter

global_config_path = path.join(path.join(path.dirname(path.dirname(path.abspath(__file__)))), '.agt.json')
logger = logging.getLogger(__name__)

# ------------------------------------------------
# Global Gadget Configuration constants
_ECHO_BLUETOOTH_ADDRESS = 'echoBluetoothAddress'
_TRANSPORT_MODE =  'transportMode'
# ------------------------------------------------

# ------------------------------------------------
# Gadget Configuration constants
_GADGET_SETTINGS = 'GadgetSettings'
_GADGET_CAPABILITIES = 'GadgetCapabilities'
_AMAZON_ID = 'amazonId'
_ALEXA_GADGET_SECRET = 'alexaGadgetSecret'
_FRIENDLY_NAME = 'friendlyName'
_MODEL_NAME = 'modelName'
_DEVICE_TOKEN_ENCRYPTION_TYPE = 'deviceTokenEncryptionType'
_FIRMWARE_VERSION = 'firmwareVersion'
_ENDPOINT_ID = 'endpointID'
_MANUFACTURER_NAME = 'manufacturerName'
_DESCRIPTION = 'description'
_VENDOR_ID = 'bluetoothVendorID'
_PRODUCT_ID = 'bluetoothProductID'

# Default values
_DEFAULT_VENDOR_ID = 'FFFF'
_DEFAULT_PRODUCT_ID = '0000'
_DEFAULT_MODEL_NAME = 'Alexa Gadget'
_DEFAULT_DEVICE_TOKEN_ENCRYPTION_TYPE = '1'
_DEFAULT_FIRMWARE_VERSION = '1'
_DEFAULT_MANUFACTURER_NAME = 'AGT'
_DEFAULT_DESCRIPTION = 'Alexa Gadget'

# Transport modes
BLE = "BLE"
BT = "BT"
# ------------------------------------------------


class AlexaGadget:
    """
    An Alexa-connected accessory that interacts with an Amazon Echo device over Classic Bluetooth or Bluetooth Low Energy.
    """

    def __init__(self, gadget_config_path=None):
        """
        Initialize gadget.

        :param gadget_config_path: (Optional) Path to your Alexa Gadget Configuration .ini file. If you don't pass this in
        then make sure you have created a file with the same prefix as your .py file and '.ini' as the suffix.
        """

        # Load the configuration file into configparser object
        self._load_gadget_config(gadget_config_path)

        # load the agt config
        self._peer_device_bt_addr = None
        self._read_peer_device_bt_address()

        # Get the radio address
        self._read_transport_mode()
        if self._transport_mode == BT:
            self.radio_address = BluetoothAdapter.get_address()
        elif self._transport_mode == BLE:
            self.radio_address = BluetoothLEAdapter.get_address()
        else:
            raise Exception('Invalid transport mode found in the config.'
                            'Please run the launch.py script with the --setup flag again '
                            'to re-configure the transport mode.')

        # Check to make sure deviceType (amazonId) and deviceTypeSecret (alexaGadgetSecret) have been configured
        self.device_type = self._get_value_from_config(_GADGET_SETTINGS, _AMAZON_ID)
        if not self.device_type:
            # if 'amazonId' is not specified, check for presence of 'deviceType' instead
            self.device_type = self._get_value_from_config(_GADGET_SETTINGS, 'deviceType')
            if self.device_type:
                logger.info('Using deprecated deviceType in configuration. Please update your .ini to use ' + _AMAZON_ID)
        if not self.device_type or self.device_type == 'YOUR_GADGET_AMAZON_ID':
            raise Exception('Please specify your ' + _AMAZON_ID + ' in ' + self.gadget_config_path)

        self.device_type_secret = self._get_value_from_config(_GADGET_SETTINGS, _ALEXA_GADGET_SECRET)
        if not self.device_type_secret:
            # if 'alexaGadgetSecret' is not specified, check for presence of 'deviceTypeSecret' instead 
            self.device_type_secret = self._get_value_from_config(_GADGET_SETTINGS, 'deviceTypeSecret')
            if self.device_type_secret:
                logger.info('Using deprecated deviceTypeSecret in configuration. Please update your .ini to use ' + _ALEXA_GADGET_SECRET)
        if not self.device_type_secret or self.device_type_secret == 'YOUR_GADGET_SECRET':
            raise Exception('Please specify your ' + _ALEXA_GADGET_SECRET + ' in ' + self.gadget_config_path)

        # Get endpoint_id from the Gadget config
        self.endpoint_id = self._get_value_from_config(_GADGET_SETTINGS, _ENDPOINT_ID)
        if not self.endpoint_id:
            self.endpoint_id = ('AGT' + self.radio_address)[:16]

        # Get friendly_name from the Gadget config
        self.friendly_name = self._get_value_from_config(_GADGET_SETTINGS, _FRIENDLY_NAME)
        if not self.friendly_name:
            self.friendly_name = 'Gadget' + self.endpoint_id[-3:]

        # Get vendor_id from the Gadget config
        vendor_id = self._get_value_from_config(_GADGET_SETTINGS, _VENDOR_ID)
        if not vendor_id:
            vendor_id = _DEFAULT_VENDOR_ID
        elif vendor_id == '0000':
            raise Exception('0000 is an invalid Vendor ID. Please use FFFF as a default, or your actual Vendor ID.')

        # Get product_id from the Gadget config
        product_id = self._get_value_from_config(_GADGET_SETTINGS, _PRODUCT_ID)
        if not product_id:
            product_id = _DEFAULT_VENDOR_ID

        # Initialize the Transport Adapter object
        if self._transport_mode == BT:
            self._bluetooth = BluetoothAdapter(self.friendly_name, vendor_id, product_id,
                                                      self._on_bluetooth_data_received,
                                                      self._on_bluetooth_connected,
                                                      self._on_bluetooth_disconnected)
        elif self._transport_mode == BLE:
            self._bluetooth = BluetoothLEAdapter(self.endpoint_id, self.friendly_name, self.device_type,
                                                 vendor_id, product_id, self._on_bluetooth_data_received,
                                                 self._on_bluetooth_connected,
                                                 self._on_bluetooth_disconnected)

        # enable auto reconnect, by default
        self._reconnect_status = (0, time.time())

        # flag for ensuring keyboard interrupt is only handled once
        self._keyboard_interrupt_being_handled = False
        # register an interrupt handler to catch 'CTRL + C'
        signal.signal(signal.SIGINT, self._keyboard_interrupt_handler)

    def main(self):
        """
        Main entry point.
        """
        # Parse the args passed in by the caller.
        parser = argparse.ArgumentParser()
        parser.add_argument('--pair', action='store_true', required=False,
        help='Puts the gadget in pairing/discoverable mode. '
        'If you are pairing to a previously paired Echo device, '
        'please ensure that you first forget the gadget from the Echo device using the Bluetooth menu in Alexa App or Echo\'s screen.')
        parser.add_argument('--clear', action='store_true', required=False,
        help='Reset gadget by unpairing bonded Echo device and clear config file. '
        'Please also forget the gadget from the Echo device using the Bluetooth menu in Alexa App or Echo\'s screen. '
        'To put the gadget in pairing mode again, use --pair')
        args = parser.parse_args()

        # If --clear is passed in, unpair Raspberry Pi with Echo Device
        if args.clear:
            # in addition to this, also unpair using bt adapter
            if self._peer_device_bt_addr is not None:
                try:
                    self._bluetooth.unpair(self._peer_device_bt_addr)
                except Exception:
                    pass
                # delete peer address in memory
                self._peer_device_bt_addr = None
                # delete peer address in config file
                self._write_peer_device_bt_address()

            logger.info('Successfully unpaired with Echo device over {}.'
                        .format(self._transport_mode) +
            ' Please also forget the gadget from the Echo device using the Bluetooth menu in Alexa App or Echo\'s screen.')
            if not args.pair:
                logger.info('To put the gadget in pairing mode again, use --pair')

        # Start pairing or reconnection only if --clear is not passed in OR if --clear is passed in with --pair argument
        if not args.clear or (args.clear and args.pair):
            # If --pair is passed in, we will only remove the BT address in memory
            if args.pair:
                # Do not delete the address in config file, this allows the customer to undo the clear
                self._peer_device_bt_addr = None

            # start the bluetooth daemon
            self.start()

            # Set discoverable if bluetooth address is not in the configuration file.
            if not self.is_paired():
                self.set_discoverable(True)
                logger.info('Now in pairing mode over {}. Pair {} in the Alexa App.'
                            .format(self._transport_mode, self.friendly_name))

            # current BT implementation requires event loop on mainthread
            # if event loop no longer required, block on signal.pause()
            self._bluetooth.run()

    def start(self):
        """
        Start gadget event loop.
        """
        # Start the Bluetooth server and event loop (Note: This doesn't connect or pair).
        self._bluetooth.start_server()
        main_thread = Thread(target=self._main_thread)
        main_thread.setDaemon(True)
        main_thread.start()

    def is_paired(self):
        """
        Return true if this gadget has a Echo device BT address in config and bonded, false otherwise
        """
        return bool(self._peer_device_bt_addr) \
            and self._bluetooth.is_paired_to_address(self._peer_device_bt_addr)

    def is_connected(self):
        """
        Return true if a Bluetooth connection to an Echo device is active, false otherwise
        """
        return self._bluetooth.is_connected()

    def set_discoverable(self, discoverable=True):
        """
        Sets whether or not an Echo device can discover and pair to this Gadget
        """
        self._bluetooth.set_discoverable(discoverable)

    def reconnect(self):
        """
        Reconnect to the paired Echo device.
        """
        # update the reconnect status to indicate that we should attempt to reconnect immediately
        self._reconnect_status = (0, time.time())

    def disconnect(self):
        """
        Disconnects, but does not un-pair, from the Echo device
        """
        # update the reconnect status to indicate that we shouldn't attempt to automatically reconnect
        self._reconnect_status = (0, None)

        # disconnect from the currently connected Echo device
        self._bluetooth.disconnect()

    def send_custom_event(self, namespace, name, payload):
        """
        Send a custom event to the skill

        :param namespace: namespace of the custom event
        :param name: name of the custom event
        :param payload: JSON payload of the custom event
        """
        event = proto.Event()
        event.header.namespace = namespace
        event.header.name = name
        event.payload = json.dumps(payload).encode('UTF-8')
        self.send_event(event)

    def send_event(self, event):
        """
        Send an event to the Echo device

        Depending on your the capabilities your gadget supports, you may call
        this method with one of the following events:

        * Alexa.Discovery.Discover.Response

          * param: `DiscoverResponseEventProto.Event <https://developer.amazon.com/docs/alexa-gadgets-toolkit/alexa-discovery-interface.html#discover-response-event>`_
        """
        msg = proto.Message()
        msg.payload = event.SerializeToString()
        logger.debug('Sending event to Echo device:\033[90m {{ {} }}\033[00m'.format(
            json_format.MessageToDict(event, including_default_value_fields=True)))
        self._bluetooth.send(msg.SerializeToString())

    # ------------------------------------------------
    # Callbacks
    # ------------------------------------------------

    def on_connected(self, device_addr):
        """
        Called when the Gadget connects to the paired Echo device.

        :param device_addr: the address of the device we connected to
        """
        pass

    def on_disconnected(self, device_addr):
        """
        Called when the Gadget disconnects from the paired Echo device.

        :param device_addr: the address of the device we disconnected from
        """
        pass

    def on_directive(self, directive):
        """
        Called when the Gadget receives a directive from the connected Echo device.

        By default, this method will call the appropriate callback method if it is defined.

        Depending on your the capabilities your gadget supports, this method may be called
        with for the following directives:

        * Alexa.Gadget.StateListener.StateUpdate

          * param: `StateUpdateDirectiveProto.Directive <https://developer.amazon.com/docs/alexa-gadgets-toolkit/alexa-gadget-statelistener-interface.html#StateUpdate-directive>`_
          * callback: ``on_alexa_gadget_statelistener_stateupdate(directive)``

        * Notifications.SetIndicator

          * param: `SetIndicatorDirectiveProto.Directive <https://developer.amazon.com/docs/alexa-gadgets-toolkit/notifications-interface.html#SetIndicator-directive>`_
          * callback: ``on_notifications_setindicator(directive)``

        * Notifications.ClearIndicator

          * param: `ClearIndicatorDirectiveProto.Directive <https://developer.amazon.com/docs/alexa-gadgets-toolkit/notifications-interface.html#ClearIndicator-directive>`_
          * callback: ``on_notifications_clearindicator(directive)``

        * Alexa.Gadget.SpeechData.Speechmarks

          * param: `SpeechmarksDirectiveProto.Directive <https://developer.amazon.com/docs/alexa-gadgets-toolkit/alexa-gadget-speechdata-interface.html#Speechmarks-directive>`_
          * callback: ``on_alexa_gadget_speechdata_speechmarks(directive)``

        * Alexa.Gadget.MusicData.Tempo

          * param: `TempoDirectiveProto.Directive <https://developer.amazon.com/docs/alexa-gadgets-toolkit/alexa-gadget-musicdata-interface.html#Tempo-directive>`_
          * callback: ``on_alexa_gadget_musicdata_tempo(directive)``

        * Alerts.SetAlert

          * param: `SetAlertDirectiveProto.Directive <https://developer.amazon.com/docs/alexa-gadgets-toolkit/alerts-interface.html#SetAlert-directive>`_
          * callback: ``on_alerts_setalert(directive)``

        * Alerts.DeleteAlert

          * param: `DeleteAlertDirectiveProto.Directive <https://developer.amazon.com/docs/alexa-gadgets-toolkit/alerts-interface.html#DeleteAlert-directive>`_
          * callback: ``on_alerts_deletealert(directive)``

        """
        logger.debug('Received directive from Echo device:\033[90m {{ {} }}\033[00m'.format(
            json_format.MessageToDict(directive, including_default_value_fields=True)))
        callback_str = 'on_' + '_'.join([directive.header.namespace, directive.header.name]).lower().replace('.', '_')
        cb = getattr(self, callback_str, None)
        if cb is not None:
            cb(directive)

    def on_alexa_discovery_discover(self, directive):
        """
        Called when Gadget receives Alexa.Discovery.Discover directive from the Echo device.
        """
        # Get values from the self.simple_gadget_config and set them to variables
        model_name = self._get_value_from_config(_GADGET_SETTINGS, _MODEL_NAME)
        if not model_name:
            model_name = _DEFAULT_MODEL_NAME

        device_token_encryption_type = self._get_value_from_config(_GADGET_SETTINGS, _DEVICE_TOKEN_ENCRYPTION_TYPE)
        if not device_token_encryption_type:
            device_token_encryption_type = _DEFAULT_DEVICE_TOKEN_ENCRYPTION_TYPE

        firmware_version = self._get_value_from_config(_GADGET_SETTINGS, _FIRMWARE_VERSION)
        if not firmware_version:
            firmware_version = _DEFAULT_FIRMWARE_VERSION

        # Automatically generate the device token using endpoint_id and device_type_secret
        device_token = self._generate_token(self.endpoint_id, self.device_type_secret)

        manufacturer_name = self._get_value_from_config(_GADGET_SETTINGS, _MANUFACTURER_NAME)
        if not manufacturer_name:
            manufacturer_name = _DEFAULT_MANUFACTURER_NAME

        description = self._get_value_from_config(_GADGET_SETTINGS, _DESCRIPTION)
        if not description:
            description = _DEFAULT_DESCRIPTION

        # Generate the Discover.Response Protocol Buffer Message
        pb_event = proto.DiscoverResponseEvent()
        pb_event.header.namespace = 'Alexa.Discovery'
        pb_event.header.name = 'Discover.Response'
        pb_event.header.messageId = ''

        # Populate the endpoint of the response payload
        pb_endpoint = pb_event.payload.endpoints.add()
        pb_endpoint.endpointId = self.endpoint_id
        pb_endpoint.manufacturerName = manufacturer_name
        pb_endpoint.description = description
        pb_endpoint.friendlyName = self.friendly_name

        pb_endpoint.additionalIdentification.modelName = model_name
        pb_endpoint.additionalIdentification.deviceTokenEncryptionType = device_token_encryption_type
        pb_endpoint.additionalIdentification.firmwareVersion = firmware_version
        pb_endpoint.additionalIdentification.amazonDeviceType = self.device_type
        pb_endpoint.additionalIdentification.radioAddress = self.radio_address
        pb_endpoint.additionalIdentification.deviceToken = device_token

        for section in self.gadget_config.sections():
            if section == _GADGET_CAPABILITIES:
                for (k, v) in self.gadget_config.items(section):
                    pb_capability = pb_endpoint.capabilities.add()
                    pb_capability.interface = k
                    pb_capability.type = 'AlexaInterface'
                    """
                    If capability is something like:
                        Alexa.Gadget.StateListener = 1.0 - timeinfo, timers, alarms, reminders, wakeword
                    Then we will split on '-' and add supported types

                    Otherwise, it should be in this format:
                        Alerts = 1.1
                    In which casse we simple pass only the version
                    """
                    if '-' in v:
                        v = v.split('-')
                        pb_capability.version = v[0].strip()
                        if len(v) == 2:
                            for st in v[1].split(','):
                                supported_types = pb_capability.configuration.supportedTypes.add()
                                supported_types.name = st.strip()
                    else:
                        pb_capability.version = v.strip()

        self.send_event(pb_event)

    # ------------------------------------------------
    # Helpers
    # ------------------------------------------------

    def _main_thread(self):
        """
        Main gadget loop.
        """
        while True:
            # poll the bluetooth adapter
            self._bluetooth.poll_server()

            # if gadget got disconnected, try to reconnect
            if not self.is_connected() and self.is_paired():
                rs = self._reconnect_status
                if rs[1] and time.time() > rs[1]:
                    logger.info(
                        'Attempting to reconnect to Echo device with address {} over {}'
                        .format(self._peer_device_bt_addr, self._transport_mode))
                    self._bluetooth.reconnect(self._peer_device_bt_addr)
                    if rs[0] < 30:
                        self._reconnect_status = (rs[0] + 1, time.time() + 10)
                    else:
                        self._reconnect_status = (rs[0] + 1, time.time() + 60)

            # 10 times a second
            time.sleep(0.1)

    def _on_bluetooth_connected(self, bt_addr):
        """
        Bluetooth connected.
        """
        logger.info('Connected to Echo device with address {} over {}'
                    .format(bt_addr, self._transport_mode))

        # Turn off pairing mode if it was enabled.
        self.set_discoverable(False)

        # reset the reconnect status
        self._reconnect_status = (0, time.time())

        # if the update the saved bluetooth address
        if bt_addr != self._peer_device_bt_addr:
            self._peer_device_bt_addr = bt_addr
            self._write_peer_device_bt_address()

        # call the callback.
        try:
            self.on_connected(bt_addr)
        except:
            logger.exception("Exception handling connect event")

    def _on_bluetooth_disconnected(self, bt_addr):
        """
        Bluetooth disconnected.
        """
        logger.info('Disconnected from Echo device with address {} over {}'
                    .format(bt_addr, self._transport_mode))

        # call the callback.
        try:
            self.on_disconnected(bt_addr)
        except:
            logger.exception("Exception handling disconnect event")

    def _on_bluetooth_data_received(self, data):
        """
        Received bluetooth data.
        """

        if not data:
            return

        # Parse the main message.
        pb_msg = proto.Message()
        try:
            pb_msg.ParseFromString(data)
        except:
            logger.error('Error handling data: {}'.format(data.hex()))
            return

        # parse the directive
        pb_directive = proto.Directive()
        pb_directive.ParseFromString(pb_msg.payload)
        namespace = pb_directive.header.namespace
        name = pb_directive.header.name
        proto_class = getattr(proto, name + 'Directive', None)
        if proto_class and namespace == proto_class.DESCRIPTOR.GetOptions().Extensions[proto.namespace]:
            pb_directive = proto_class()
            pb_directive.ParseFromString(pb_msg.payload)

        # call the callback.
        try:
            self.on_directive(pb_directive)
        except:
            logger.exception("Exception handling directive from Echo device")

    def _load_gadget_config(self, gadget_config_path):
        """
        If a path for the Gadget configuration .ini is passed in, then it will load that. Otherwise, if there is a
        .ini file with the same prefix and the main .py file, then it will load that. Otherwise, an exception is thrown
        asking the user to create the .ini file.

        :param gadget_config_path:
        """
        self.gadget_config_path = gadget_config_path
        if not gadget_config_path:
            # If no config file was passed in the constructor, then look for a file with the same as the .py file
            gadget_config_path = sys.modules[self.__module__].__file__
            self.gadget_config_path = gadget_config_path.replace('.py', '.ini')

        # Make sure the config file exists and read it into the configparser
        if path.exists(self.gadget_config_path):
            self.gadget_config = configparser.ConfigParser()
            self.gadget_config.optionxform = str
            self.gadget_config.read([self.gadget_config_path])
        else:
            raise Exception('Please make sure you have created ' + self.gadget_config_path)

    def _get_value_from_config(self, section, option):
        """
        Gets a value from the Gadget .ini file.

        :param section:
        :param option:
        :return: value or None
        """
        if self.gadget_config.has_option(section, option):
            return self.gadget_config.get(section, option)
        return None

    def _read_transport_mode(self):
        """
        Reads the transport mode with which gadget is configured
        """
        try:
            with open(global_config_path, "r") as read_file:
                data = json.load(read_file)
                self._transport_mode = data.get(_TRANSPORT_MODE, None)
        except:
            raise Exception('Transport mode is not configured for the gadget.'
                            'Please run the launch.py script with the --setup flag.')

    def _read_peer_device_bt_address(self):
        """
        Reads the bluetooth address of the paired Echo device from disk
        """
        try:
            with open(global_config_path, "r") as read_file:
                data = json.load(read_file)
                self._peer_device_bt_addr = data.get(_ECHO_BLUETOOTH_ADDRESS, None)
        except:
            self._peer_device_bt_addr = None

    def _write_peer_device_bt_address(self):
        """
        Writes the bluetooth address of the paired Echo device to disk
        """
        with open(global_config_path, "r") as read_file:
            data = json.load(read_file)
        with open(global_config_path, "w+") as write_file:
            data[_ECHO_BLUETOOTH_ADDRESS] = self._peer_device_bt_addr
            json.dump(data, write_file)

    def _generate_token(self, device_id, device_token):
        """
        Generates the device secret for the given device id and device type secret
        """
        hash_object = hashlib.sha256(bytes(device_id, 'utf-8') + bytes(device_token, 'utf-8'))
        hex_dig = hash_object.hexdigest()
        return bytes(hex_dig, 'utf-8')

    def _keyboard_interrupt_handler(self, signal, frame):
        if not self._keyboard_interrupt_being_handled:
            self._keyboard_interrupt_being_handled = True
            self._bluetooth.set_discoverable(False)
            self._bluetooth.stop_server()
