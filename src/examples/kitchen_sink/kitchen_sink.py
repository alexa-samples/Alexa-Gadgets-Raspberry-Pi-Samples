#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

import logging
import sys

from agt import AlexaGadget

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('agt.alexa_gadget').setLevel(logging.DEBUG)

class KitchenSinkGadget(AlexaGadget):
    """
    Class that logs each directive received from the Echo device.
    """

    def on_connected(self, device_addr):
        """
        Gadget connected to the paired Echo device.

        :param device_addr: the address of the device we connected to
        """
        pass

    def on_disconnected(self, device_addr):
        """
        Gadget disconnected from the paired Echo device.

        :param device_addr: the address of the device we disconnected from
        """
        pass

    def on_alexa_gadget_statelistener_stateupdate(self, directive):
        """
        Alexa.Gadget.StateListener StateUpdate directive received.

        For more info, visit:
            https://developer.amazon.com/docs/alexa-gadgets-toolkit/alexa-gadget-statelistener-interface.html#StateUpdate-directive

        :param directive: Protocol Buffer Message that was send by Echo device.

        To get the specific state update name, the following code snippet can be used:
        # Extract first available state (name & value) from directive payload
        if len(directive.payload.states) > 0:
            state = directive.payload.states[0]
            name = state.name
            value = state.value
            print('state name:{}, state value:{}'.format(name, value))

        """
        pass

    def on_notifications_setindicator(self, directive):
        """
        Notifications SetIndicator directive received.

        For more info, visit:
            https://developer.amazon.com/docs/alexa-gadgets-toolkit/notifications-interface.html#SetIndicator-directive

        :param directive: Protocol Buffer Message that was send by Echo device.
        """
        pass

    def on_notifications_clearindicator(self, directive):
        """
        Notifications ClearIndicator directive received.

        For more info, visit:
            https://developer.amazon.com/docs/alexa-gadgets-toolkit/notifications-interface.html#ClearIndicator-directive

        :param directive: Protocol Buffer Message that was send by Echo device.
        """
        pass

    def on_alexa_gadget_speechdata_speechmarks(self, directive):
        """
        Alexa.Gadget.SpeechData Speechmarks directive received.

        For more info, visit:
            https://developer.amazon.com/docs/alexa-gadgets-toolkit/alexa-gadget-speechdata-interface.html#Speechmarks-directive

        :param directive: Protocol Buffer Message that was send by Echo device.
        """
        pass

    def on_alexa_gadget_musicdata_tempo(self, directive):
        """
        Alexa.Gadget.MusicData Tempo directive received.

        For more info, visit:
            https://developer.amazon.com/docs/alexa-gadgets-toolkit/alexa-gadget-musicdata-interface.html#Tempo-directive

        :param directive: Protocol Buffer Message that was send by Echo device.
        """
        pass

    def on_alerts_setalert(self, directive):
        """
        Alerts SetAlert directive received.

        For more info, visit:
            https://developer.amazon.com/docs/alexa-gadgets-toolkit/alerts-interface.html#SetAlert-directive

        :param directive: Protocol Buffer Message that was send by Echo device.
        """
        pass

    def on_alerts_deletealert(self, directive):
        """
        Alerts DeleteAlert directive received.

        For more info, visit:
            https://developer.amazon.com/docs/alexa-gadgets-toolkit/alerts-interface.html#DeleteAlert-directive

        :param directive: Protocol Buffer Message that was send by Echo device.
        """
        pass


if __name__ == '__main__':
    KitchenSinkGadget().main()
