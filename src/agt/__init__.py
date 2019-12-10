#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

"""
The Alexa Gadgets Toolkit Python API allows you to build fun and delightful accessories
that pair to compatible Echo devices via Classic Bluetooth or Bluetooth Low Energy. These accessories can
extend Alexa’s capabilities to new modalities with motors, lights, sound chips,
and more.

.. highlight:: python
.. code-block:: python

    from agt import AlexaGadget

    class MyFirstGadget(AlexaGadget):
        def on_alexa_gadget_statelistener_stateupdate(self, directive):
            print("STATE UPDATED: ", directive)

    if __name__ == '__main__':
        MyFirstGadget().main()

"""
# Core API
from agt.alexa_gadget import AlexaGadget

# Directives
from agt.messages_pb2 import Directive
from agt.messages_pb2 import ClearIndicatorDirective
from agt.messages_pb2 import DeleteAlertDirective
from agt.messages_pb2 import DiscoverDirective
from agt.messages_pb2 import SetAlertDirective
from agt.messages_pb2 import SetIndicatorDirective
from agt.messages_pb2 import SpeechmarksDirective
from agt.messages_pb2 import StateUpdateDirective
from agt.messages_pb2 import TempoDirective

# Events
from agt.messages_pb2 import Event
from agt.messages_pb2 import DiscoverResponseEvent

