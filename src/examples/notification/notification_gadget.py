#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

import logging
import sys
import time

from gpiozero import AngularServo

from agt import AlexaGadget

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

GPIO_PIN = 25

SERVO = AngularServo(GPIO_PIN, initial_angle=-90, min_pulse_width=0.0005, max_pulse_width=0.002)

class NotificationGadget(AlexaGadget):
    """
    An Alexa Gadget that rotates a servo to raise and lower a flag when a
    notification is received or cleared on a paired Echo device
    """

    def __init__(self):
        super().__init__()

    def on_notifications_setindicator(self, directive):
        logger.info('Notification set - set servo to 0 degrees')

        # Set angle of servo to 0 degrees
        SERVO.angle = 0
        time.sleep(1)
        SERVO.detach()

    def on_notifications_clearindicator(self, directive):
        logger.info('Notification cleared - set servo to -90 degrees')

        # Set angle of servo to -90 degrees
        SERVO.angle = -90
        time.sleep(1)
        SERVO.detach()


if __name__ == '__main__':
    try:
        NotificationGadget().main()
    finally:
        logger.debug('Cleaning up GPIO')
        SERVO.close()
