#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

import logging
import sys
from gpiozero import LED

from agt import AlexaGadget

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

GPIO_PIN = 14

LED = LED(GPIO_PIN)

class WakewordGadget(AlexaGadget):
    """
    An Alexa Gadget that turns an LED on and off in sync with the detection
    of the wake word
    """

    def __init__(self):
        super().__init__()

    def on_alexa_gadget_statelistener_stateupdate(self, directive):
        for state in directive.payload.states:
            if state.name == 'wakeword':
                if state.value == 'active':
                    logger.info('Wake word active - turn on LED')
                    LED.on()
                elif state.value == 'cleared':
                    logger.info('Wake word cleared - turn off LED')
                    LED.off()


if __name__ == '__main__':
    try:
        WakewordGadget().main()
    finally:
        logger.debug('Cleaning up GPIO')
        LED.close()
