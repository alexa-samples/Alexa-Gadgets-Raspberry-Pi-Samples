# Kitchen Sink Gadget Example

**This guide steps through the process of creating an Alexa Gadget that prints messages to the command line based on directives received from a paired Echo device.**

## Prerequisites

In order to to run this example **you should already have** a Raspberry Pi with the **Alexa-Gadgets-Raspberry-Pi-Samples software** installed. Learn more in the [project README](../../../README.md).

## Step 1: Configure your credentials

As with any example, you'll need to first add the credentials that are associated with the gadget you created in the [Alexa Voice Service Developer Console](https://developer.amazon.com/avs/home.html#/avs/home):

1. On the command line of your Pi, navigate to `/home/pi/Alexa-Gadgets-Raspberry-Pi-Samples/src/examples/kitchen_sink`
2. Open the `kitchen_sink.ini` file within that folder.
3. Change the `amazonId` from `YOUR_GADGET_AMAZON_ID` to the **Amazon ID** that is displayed on the gadget's product page in the Alexa Voice Service Developer Console.
4. Change the `alexaGadgetSecret` from `YOUR_GADGET_SECRET` to the **Alexa Gadget Secret** that is displayed on the gadget's product page in the Alexa Voice Service Developer Console.

You can also use the launch script's setup mode to configure all the credentials for all the examples at once as follows:
* Start the launch script in setup mode
    ```
    sudo python3 launch.py --setup
    ```
* Enter *'y'* when prompted for configuring the gadget credentials; and enter the `amazonId` and `alexaGadgetSecret` that is displayed on the gadget's product page in the Alexa Voice Service Developer Console.

    ![Pi CLI Screenshot 1](../../../docs/_static/images/pi_cli_screenshot_1.png)

To learn more, refer to [Register a Gadget](https://developer.amazon.com/docs/alexa-gadgets-toolkit/register-gadget.html) in the Alexa Gadgets Toolkit documentation.

## Step 2: Run the example

In order for this gadget to function, it will need to be paired to a [compatible Echo device](https://developer.amazon.com/docs/alexa-gadgets-toolkit/overview-bluetooth-gadgets.html#device-bluetooth-support). Before running the example, refer to the [pairing guide](../../../README.md) to learn how to pair your gadget.

With your Echo device nearby, run the launch script with the `--example` argument and specify *'kitchen_sink'* as the example name:

```
sudo python3 launch.py --example kitchen_sink
```

If your gadget has not paired before, your gadget will automatically attempt to pair.

Once paired, try the following commands:

*"Alexa, set a timer for 10 seconds"*

*"Alexa, play music"*

*"Alexa, ask [Quote Maker](https://developer.amazon.com/docs/alexa-voice-service/notifications-overview.html#enable-the-quote-maker-skill-for-testing) to send a notification"*

For each of these commands, you will see a directive logged to the command line. For example, when a timer is set:

```
{ {'payload': {'type': 'TIMER', 'token': '853514641', 'scheduledTime': '2019-03-25T14:44:51-07:00'}, 'header': {'namespace': 'Alerts', 'name': 'SetAlert'}} }
```

You will also see directives when:

- The wake word is spoken
- When Alexa is speaking (visemes)
- When a timesync event takes place

For example, when the wake word is detected:

```
{ {'payload': {'states': [{'value': 'active', 'name': 'wakeword'}]}, 'header': {'namespace': 'Alexa.Gadget.StateListener', 'name': 'StateUpdate'}} }
```

Now that you can see these directives, you can modify the code within the callbacks defined in the Python code. You can learn more about these callbacks in the [project README](../../../README.md).

## How does this work?

This example follows the same model called out in [project README](../../../README.md). The configuration, and callbacks within the Python code, define how this gadget should work.

### Configuration

Within the `kitchen_sink.ini` file, you will see the `Amazon ID` and `Alexa Gadget Secret` defined, as well as the capabilities that the gadget is set to respond to:

```
[GadgetSettings]
amazonId = YOUR_GADGET_AMAZON_ID
alexaGadgetSecret = YOUR_GADGET_SECRET

[GadgetCapabilities]
Alexa.Gadget.StateListener = 1.0 - timeinfo, timers, alarms, reminders, wakeword
Alerts = 1.1
Notifications = 1.0
Alexa.Gadget.MusicData = 1.0 - tempo
Alexa.Gadget.SpeechData = 1.0 - viseme
```

The Kitchen Sink example responds to all the Alexa Gadget Toolkit capabilities that are available, which you can see listed. You can learn more about the various capabilities in [the documentation](https://developer.amazon.com/docs/alexa-gadgets-toolkit/features.html).

### Code

Within `kitchen_sink.py` you'll notice the callbacks that are used, which map directly to the capabilities that the gadget is configured to respond to:

```python
def on_connected(self, device_addr):
    pass

def on_disconnected(self, device_addr):
    pass

def on_alexa_gadget_statelistener_stateupdate(self, directive):
    pass

def on_notifications_setindicator(self, directive):
    pass

def on_notifications_clearindicator(self, directive):
    pass

def on_alexa_gadget_speechdata_speechmarks(self, directive):
    pass

def on_alexa_gadget_musicdata_tempo(self, directive):
    pass

def on_alerts_setalert(self, directive):
    pass

def on_alerts_deletealert(self, directive):
    pass
```

In this example, a message is logged to the command line for each directive that is received from the Echo device. This is where you can add new ways for your gadget to respond, like lighting an LED, moving a servo, etc.

## What's next

Now that you've successfully set up your Raspberry Pi as a gadget, you can begin to customize it. You can either continue to build an example, or build your own.

To build your own project, simply duplicate one of the examples. Then, you can modify the example config and Python code to specify how your gadget reacts to different incoming messages. You can run your project the same way you ran the example →  `sudo python3 launch.py --example YOUR_EXAMPLE_NAME`

To learn more about Alexa Gadgets Toolkit capabilities, [review the documentation](https://developer.amazon.com/docs/alexa-gadgets-toolkit/features.html).
