# Color Cycler Gadget - Python Sample Skill

**This guide steps through the process of creating an Alexa Gadget with an LED and a button, that cycles through different colors and reports the LED color when the button is pressed.**

The following is a brief overview of the **Python version** companion sample skill for your gadget.

Follow the instructions in the [main README file](../../README.md) for instructions on how to deploy this skill to your account, or for information about how to deploy the sample gadget code on to your Raspberri Pi.


### Explore the lambda code

The custom skill lambda code in `lambda\lambda_function.py` uses [ASK SDK for Python](https://developer.amazon.com/docs/sdk/alexa-skills-kit-sdk-for-python.html) for processing and responding to all skill requests. This section will elaborate more on the use of custom interfaces in the lambda code for this example.

#### Supporting functions

First, notice that the `get_connected_endpoints` function in the lambda code makes and HTTPS request to the [Endpoint Enumeration API](https://developer.amazon.com/docs/alexa-gadgets-toolkit/send-gadget-custom-directive-from-skill.html#call-endpoint-enumeration-api) to get the list of gadget endpoints connected to the Echo device.

```python
def get_connected_endpoints(handler_input: HandlerInput):
    return handler_input.service_client_factory.get_endpoint_enumeration_service().get_endpoints().endpoints
```

Next, notice the `build_blink_led_directive` function used for building the `BlinkLED` directive of the custom interface `Custom.ColorCyclerGadget`, which would animate the gadget's RGB LED based on the parameters being sent.

```python
def build_blink_led_directive(endpoint_id, colors_list, intervalMs, iterations, startGame):
    return SendDirectiveDirective(
        header=Header(namespace='Custom.ColorCyclerGadget', name='BlinkLED'),
        endpoint=Endpoint(endpoint_id=endpoint_id),
        payload={
            'colors_list': colors_list,
            'intervalMs': intervalMs,
            'iterations': iterations,
            'startGame': startGame
        }
    )
```

Similarly, notice the `build_stop_led_directive` function used for building the `StopLED` directive of the custom interface `Custom.ColorCyclerGadget`, which would stop the gadget's RGB LED animation.

```python
def build_stop_led_directive(endpoint_id):
    return SendDirectiveDirective(
        header=Header(namespace='Custom.ColorCyclerGadget', name='StopLED'),
        endpoint=Endpoint(endpoint_id=endpoint_id),
        payload={}
    )
```

Next, notice the `buildStartEventHandlerDirective()` function used for building the [CustomInterfaceController.StartEventHandler](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#start) directive that would start the event handler for receiving the custom events on skill-side sent from the gadget.

```python
def build_start_event_handler_directive(token, duration_ms, namespace,
                                        name, filter_match_action, expiration_payload):
    return StartEventHandlerDirective(
        token=token,
        event_filter=EventFilter(
            filter_expression={
                'and': [
                    {'==': [{'var': 'header.namespace'}, namespace]},
                    {'==': [{'var': 'header.name'}, name]}
                ]
            },
            filter_match_action=filter_match_action
        ),
        expiration=Expiration(
            duration_in_milliseconds=duration_ms,
            expiration_payload=expiration_payload))
```

Finally, notice the `buildStopEventHandlerDirective()` function used for building the [CustomInterfaceController.StopEventHandler](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#stop) directive that would stop the event handler having the specified `token`.

```python
def build_stop_event_handler_directive(token):
    return StopEventHandlerDirective(token=token)
```

#### Skill flow in lambda

When the custom skill is launched, a `LaunchRequest` request is received by the skill lambda. The `apiEndpoint` and `apiAccessToken` are obtained from the request as follows, in the `launch_request_handler` function:

```python
system = handler_input.request_envelope.context.system
api_access_token = system.api_access_token
api_endpoint = system.api_endpoint
```

Then, the gadget endpoints are obtained using the `get_connected_endpoints` function discussed above:

```python
# Get connected gadget endpoint ID.
endpoints = get_connected_endpoints(handler_input)
```

For this example, as you will have only one gadget connected to the Echo device, its endpointId will be retrieved and stored in the [skill session attributes](https://developer.amazon.com/docs/custom-skills/manage-skill-session-and-session-attributes.html#save-data-during-the-session) for using it later to send directives to gadget.

```python
endpoint_id = endpoints[0]['endpointId']

# Store endpoint ID for using it to send custom directives later.
logger.debug("Received endpoints. Storing Endpoint Id: %s", endpoint_id)
session_attr = handler_input.attributes_manager.session_attributes
session_attr['endpointId'] = endpoint_id
```

The skill lambda will then send the `BlinkLED` directive to your gadget endpoint to make its LED display the color green for the next 20 seconds, and wait for voice input from the users to confirm if they are ready for the game.

```python
# Send the BlindLEDDirective to make the LED green for 20 seconds.
return (response_builder
        .speak("Hi! I will cycle through a spectrum of colors. " +
                "When you press the button, I'll report back which color you pressed. Are you ready?")
        .add_directive(build_blink_led_directive(endpoint_id, ['GREEN'], 1000, 20, False))
        .set_should_end_session(False)
        .response)
```

If the user replies *'Yes'*, the `AMAZON.YesIntent` intent request will be received by the skill lambda. As a response to this request, a `BlinkLED` directive will be sent to the gadget, having the endpointId which is retrieved from SessionAttributes, to animate the gadget's RGB LED for it to cycle through a list of colors with an interval of 1 second.
A [CustomInterfaceController.StartEventHandler](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#start) directive will also be sent to start an event handler for 10 seconds to receive a single `ReportColor` event and terminate the event handler once the event is received.

```python
# Retrieve the stored gadget endpoint ID from the SessionAttributes.
session_attr = handler_input.attributes_manager.session_attributes
endpoint_id = session_attr['endpointId']

# Create a token to be assigned to the EventHandler and store it
# in session attributes for stopping the EventHandler later.
token = str(uuid.uuid4())
session_attr['token'] = token

response_builder = handler_input.response_builder

# Send the BlindLED Directive to trigger the cycling animation of the LED.
# and, start a EventHandler for 10 seconds to receive only one
return (response_builder
        .add_directive(build_blink_led_directive(endpoint_id,
                                                    ['RED', 'YELLOW', 'GREEN', 'CYAN',
                                                    'BLUE', 'PURPLE', 'WHITE'],
                                                    1000, 2, True))
        .add_directive(build_start_event_handler_directive(token, 10000,
                                                            'Custom.ColorCyclerGadget', 'ReportColor',
                                                            FilterMatchAction.SEND_AND_TERMINATE,
                                                            {'data': "You didn't press the button. Good bye!"}))
        .response)
```

If you press the gadget's button before the event handler expires, the skill lambda will receive the `ReportColor` event as a request of type [CustomInterfaceController.EventsReceived](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#received). Upon receiving the event, first the skill lambda validates that the event has been received for the currently active event handler and that the event has the name `ReportColor` under the namespace `Custom.ColorCyclerGadget`. As a response to the event, the skill speaks the reported color and ends the skill session.

```python
request = handler_input.request_envelope.request
session_attr = handler_input.attributes_manager.session_attributes
response_builder = handler_input.response_builder

# Validate event handler token
if session_attr['token'] != request.token:
    logger.info("EventHandler token doesn't match. Ignoring this event.")
    return (response_builder
            .speak("EventHandler token doesn't match. Ignoring this event.")
            .response)

custom_event = request.events[0]
payload = custom_event.payload
namespace = custom_event.header.namespace
name = custom_event.header.name

if namespace == 'Custom.ColorCyclerGadget' and name == 'ReportColor':
    # On receipt of 'Custom.ColorCyclerGadget.ReportColor' event, speak the reported color
    # and end skill session.
    return (response_builder
            .speak(payload['color'] + ' is the selected color. Thank you for playing. Good bye!')
            .set_should_end_session(True)
            .response)

return response_builder.response
```

If you don't press the gadget's button within 10 seconds, the event handler will expire and the skill lambda will receive the [CustomInterfaceController.Expired](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#expired) request. Also, if the user initially replies *'No'* to the *'Are you ready?'* skill prompt, the `AMAZON.NoIntent` intent request will be received by the skill lambda. Additionally, if the user stops or cancels the skill, the `AMAZON.StopIntent` or `AMAZON.CancelIntent` intent request will be received by the skill lambda.

As a response to any of these requests, the skill lambda sends a `StopLED` directive to stop the LED animations on the gadget and ends the skill session.

```python
request = handler_input.request_envelope.request
response_builder = handler_input.response_builder
session_attr = handler_input.attributes_manager.session_attributes
endpoint_id = session_attr['endpointId']

# When the EventHandler expires, send StopLED directive to stop LED animation
# and end skill session.
return (response_builder
        .add_directive(build_stop_led_directive(endpoint_id))
        .speak(request.expiration_payload['data'])
        .set_should_end_session(True)
        .response)
```