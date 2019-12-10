#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
#

import json
import logging
import sys
import threading
import time

from gpiozero import RGBLED, Button
from colorzero import Color
from agt import AlexaGadget

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# GPIO Pins
GPIO_LED_RED = 2
GPIO_LED_GREEN = 3
GPIO_LED_BLUE = 4
GPIO_BUTTON = 14

# Setup RGB LED
# set active_high to False for common anode RGB LED
# else set to True for common cathode RGB LED
RGB_LED = RGBLED(GPIO_LED_RED, GPIO_LED_GREEN, GPIO_LED_BLUE,
                 active_high=False, initial_value=(0, 0, 0))

# Setup Button
BUTTON = Button(GPIO_BUTTON)


class ColorCyclerGadget(AlexaGadget):
    """
    An Alexa Gadget that cycles through colors using RGB LED and
    reports the color to the skill upon button press
    """

    def __init__(self):
        super().__init__()

        # Color animation states
        self.color = None
        self.colors_list = []
        self.interval_ms = 0
        self.iterations = 0
        self.cycle_count = 0
        self.keep_cycling = False
        self.game_active = False

        # Setup a lock to be used for avoiding race conditions
        # during color animation state updates
        self.lock = threading.Lock()
        # Setup a separate thread for LED to cycle through colors
        self.led_thread = threading.Thread(target=self._led_blink)
        self.led_thread.start()

        BUTTON.when_pressed = self._button_pressed

    def on_custom_colorcyclergadget_blinkled(self, directive):
        """
        Handles Custom.ColorCyclerGadget.BlinkLED directive sent from skill
        by triggering LED color cycling animations based on the received parameters
        """
        payload = json.loads(directive.payload.decode("utf-8"))

        logger.info('BlinkLED directive received: LED will cycle through ' + str(payload['colors_list']) + ' colors')

        self.lock.acquire()
        # Initialize the color animation states based on parameters received from skill
        self.colors_list = payload['colors_list']
        self.interval_ms = payload['intervalMs']
        self.iterations = payload['iterations']
        self.cycle_count = 0
        self.game_active = bool(payload['startGame'])
        self.keep_cycling = True
        self.lock.release()

    def on_custom_colorcyclergadget_stopled(self, directive):
        """
        Handles Custom.ColorCyclerGadget.StopLED directive sent from skill
        by stopping the LED animations
        """
        logger.info('StopLED directive received: Turning off LED')

        # Turn off the LED and disable the color animation states to stop the LED cycling animation
        RGB_LED.off()
        self.lock.acquire()
        self.keep_cycling = False
        self.game_active = False
        self.lock.release()

    def _button_pressed(self):
        """
        Callback to report the LED color to the skill when the button is pressed
        """
        if self.game_active:
            logger.info('Button Pressed: Current color = ' + self.color)

            # Send custom event to skill with the color of the LED
            payload = {'color': self.color}
            self.send_custom_event(
                'Custom.ColorCyclerGadget', 'ReportColor', payload)

            self.lock.acquire()
            # Stop the LED cycling animation
            self.keep_cycling = False
            self.lock.release()

    def _led_blink(self):
        """
        Plays the LED cycling animation based on the color animation states
        """
        while True:
            # If cycling animation is still active
            if self.keep_cycling and self.cycle_count < len(self.colors_list) * self.iterations:
                self.lock.acquire()
                self.color = self.colors_list[self.cycle_count
                                              % len(self.colors_list)]
                self.cycle_count = self.cycle_count + 1
                self.lock.release()

                # Set the color for the LED
                RGB_LED.color = Color(self.color.lower())

                # Display the color for specified interval before switching again
                time.sleep(self.interval_ms/1000)

            # If button is pressed, display the current color for 5 seconds
            elif not self.keep_cycling and self.game_active:
                time.sleep(5)
                RGB_LED.off()
                self.lock.acquire()
                self.game_active = False
                self.lock.release()
            else:
                RGB_LED.off()
                time.sleep(0.1)


if __name__ == '__main__':
    try:
        ColorCyclerGadget().main()
    finally:
        RGB_LED.close()
        BUTTON.close()
