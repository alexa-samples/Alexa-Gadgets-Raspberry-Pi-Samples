# Color Cycler Gadget - NodeJS Sample Skill

**This guide steps through the process of creating an Alexa Gadget with an LED and a button, that cycles through different colors and reports the LED color when the button is pressed.**

The following is a brief overview of the **NodeJS version** companion sample skill for your gadget.

Follow the instructions in the [main README file](../../README.md) for instructions on how to deploy this skill to your account, or for information about how to deploy the sample gadget code on to your Raspberri Pi.


### Explore the lambda code

The custom skill lambda code in `lambda\custom\index.js` uses [ASK SDK for NodeJS](https://developer.amazon.com/docs/alexa-skills-kit-sdk-for-nodejs/overview.html) for processing and responding to all skill requests. This section will elaborate more on the use of custom interfaces in the lambda code for this example.

#### Supporting functions

First, notice that the `getConnectedEndpointsResponse()` function in the lambda code uses an HTTPS GET request to the [Endpoint Enumeration API](https://developer.amazon.com/docs/alexa-gadgets-toolkit/send-gadget-custom-directive-from-skill.html#call-endpoint-enumeration-api) to get the list of gadget endpoints connected to the Echo device.
```javascript
function getConnectedEndpointsResponse(handlerInput) {
    return handlerInput.serviceClientFactory.getEndpointEnumerationServiceClient().getEndpoints();
}
```

Next, notice the `buildBlinkLEDDirective()` function used for building the `BlinkLED` directive of the custom interface `Custom.ColorCyclerGadget`, which would animate the gadget's RGB LED based on the parameters being sent.

```javascript
function buildBlinkLEDDirective(endpointId, colors_list, intervalMs, iterations, startGame) {
    return {
        type: 'CustomInterfaceController.SendDirective',
        header: {
            name: 'BlinkLED',
            namespace: 'Custom.ColorCyclerGadget'
        },
        endpoint: {
            endpointId: endpointId
        },
        payload: {
            colors_list: colors_list,
            intervalMs: intervalMs,
            iterations: iterations,
            startGame: startGame
        }
    };
}
```

Similarly, notice the `buildStopLEDDirective()` function used for building the `StopLED` directive of the custom interface `Custom.ColorCyclerGadget`, which would stop the gadget's RGB LED animation.

```javascript
function buildStopLEDDirective(endpointId) {
    return {
        type: 'CustomInterfaceController.SendDirective',
        header: {
            name: 'StopLED',
            namespace: 'Custom.ColorCyclerGadget'
        },
        endpoint: {
            endpointId: endpointId
        },
        payload: {}
    };
}
```

Next, notice the `buildStartEventHandlerDirective()` function used for building the [CustomInterfaceController.StartEventHandler](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#start) directive that would start the event handler for receiving the custom events on skill-side sent from the gadget.

```javascript
function buildStartEventHandlerDirective(token, durationMs, namespace, name, filterMatchAction, expirationPayload) {
    return {
        type: "CustomInterfaceController.StartEventHandler",
        token: token,
        eventFilter: {
            filterExpression: {
                'and': [
                    { '==': [{ 'var': 'header.namespace' }, namespace] },
                    { '==': [{ 'var': 'header.name' }, name] }
                ]
            },
            filterMatchAction: filterMatchAction
        },
        expiration: {
            durationInMilliseconds: durationMs,
            expirationPayload: expirationPayload
        }
    };
}
```

Finally, notice the `buildStopEventHandlerDirective()` function used for building the [CustomInterfaceController.StopEventHandler](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#stop) directive that would stop the event handler having the specified `token`.

```javascript
function buildStopEventHandlerDirective(token) {
    return {
        type: "CustomInterfaceController.StopEventHandler",
        token: token
    };
}
```

#### Skill flow in lambda

When the custom skill is launched, a `LaunchRequest` request is received by the skill lambda. The `apiEndpoint` and `apiAccessToken` are obtained from the request as follows:
```javascript
let { context } = handlerInput.requestEnvelope;
let { apiEndpoint, apiAccessToken } = context.System;
```

Then, the gadget endpoints response are obtained using the `getConnectedEndpointsResponse()` function:
```javascript
response = await getConnectedEndpointsResponse(handlerInput);
```

For this example, as you will have only one gadget connected to the Echo device, its endpointId will be retrieved and stored in the [skill session attributes](https://developer.amazon.com/docs/custom-skills/manage-skill-session-and-session-attributes.html#save-data-during-the-session) for using it later to send directives to gadget.
```javascript
let endpointId = response.endpoints[0].endpointId;

// Store endpointId for using it to send custom directives later.
console.log("Received endpoints. Storing Endpoint Id: " + endpointId);
const attributesManager = handlerInput.attributesManager;
let sessionAttributes = attributesManager.getSessionAttributes();
sessionAttributes.endpointId = endpointId;  
attributesManager.setSessionAttributes(sessionAttributes);
```

The skill lambda will then send the `BlinkLED` directive to your gadget endpoint to make its LED display the color green for the next 20 seconds, and wait for voice input from the users to confirm if they are ready for the game.

```javascript
return handlerInput.responseBuilder
    .speak("Hi! I will cycle through a spectrum of colors. " +
        "When you press the button, I'll report back which color you pressed. Are you ready?")
    .withShouldEndSession(false)
    // Send the BlindLEDDirective to make the LED green for 20 seconds.
    .addDirective(buildBlinkLEDDirective(endpointId, ['GREEN'], 1000, 20, false))
    .getResponse();
```

If the user replies *'Yes'*, the `AMAZON.YesIntent` intent request will be received by the skill lambda. As a response to this request, a `BlinkLED` directive will be sent to the gadget, having the endpointId which is retrieved from SessionAttributes, to animate the gadget's RGB LED for it to cycle through a list of colors with an interval of 1 second.
A [CustomInterfaceController.StartEventHandler](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#start) directive will also be sent to start an event handler for 10 seconds to receive a single `ReportColor` event and terminate the event handler once the event is received.

```javascript
// Retrieve the stored gadget endpointId from the SessionAttributes.
const attributesManager = handlerInput.attributesManager;
let sessionAttributes = attributesManager.getSessionAttributes();
let endpointId = sessionAttributes.endpointId;

// Create a token to be assigned to the EventHandler and store it
// in session attributes for stopping the EventHandler later.
sessionAttributes.token = Uuid();
attributesManager.setSessionAttributes(sessionAttributes);

console.log("YesIntent received. Starting game.");

return handlerInput.responseBuilder
    // Send the BlindLEDDirective to trigger the cycling animation of the LED.
    .addDirective(buildBlinkLEDDirective(endpointId, ['RED', 'YELLOW', 'GREEN', 'CYAN', 'BLUE', 'PINK', 'WHITE'],
        1000, 2, true))
    // Start a EventHandler for 10 seconds to receive only one
    // 'Custom.ColorCyclerGadget.ReportColor' event and terminate.
    .addDirective(buildStartEventHandlerDirective(sessionAttributes.token, 10000,
        'Custom.ColorCyclerGadget', 'ReportColor', 'SEND_AND_TERMINATE',
        { 'data': "You didn't press the button. Good bye!" }))
    .getResponse();
```

If you press the gadget's button before the event handler expires, the skill lambda will receive the `ReportColor` event as a request of type [CustomInterfaceController.EventsReceived](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#received). Upon receiving the event, first the skill lambda validates that the event has been received for the currently active event handler and that the event has the name `ReportColor` under the namespace `Custom.ColorCyclerGadget`. As a response to the event, the skill speaks the reported color and ends the skill session.
```javascript
let { request } = handlerInput.requestEnvelope;

const attributesManager = handlerInput.attributesManager;
let sessionAttributes = attributesManager.getSessionAttributes();

// Validate eventHandler token
if (sessionAttributes.token !== request.token) {
    console.log("EventHandler token doesn't match. Ignoring this event.");
    return handlerInput.responseBuilder
        .speak("EventHandler token doesn't match. Ignoring this event.")
        .getResponse();
}

let customEvent = request.events[0];
let payload = customEvent.payload;
let namespace = customEvent.header.namespace;
let name = customEvent.header.name;

let response = handlerInput.responseBuilder;

if (namespace === 'Custom.ColorCyclerGadget' && name === 'ReportColor') {
    // On receipt of 'Custom.ColorCyclerGadget.ReportColor' event, speak the reported color
    // and end skill session.
    return response.speak(payload.color + ' is the selected color. Thank you for playing. Good bye!')
        .withShouldEndSession(true)
        .getResponse();
}
return response;
```

If you don't press the gadget's button within 10 seconds, the event handler will expire and the skill lambda will receive the [CustomInterfaceController.Expired](https://developer.amazon.com/docs/alexa-gadgets-toolkit/receive-custom-event-from-gadget.html#expired) request. Also, if the user initially replies *'No'* to the *'Are you ready?'* skill prompt, the `AMAZON.NoIntent` intent request will be received by the skill lambda. Additionally, if the user stops or cancels the skill, the `AMAZON.StopIntent` or `AMAZON.CancelIntent` intent request will be received by the skill lambda.

As a response to any of these requests, the skill lambda sends a `StopLED` directive to stop the LED animations on the gadget and ends the skill session.
```javascript
let { request } = handlerInput.requestEnvelope;

const attributesManager = handlerInput.attributesManager;
let sessionAttributes = attributesManager.getSessionAttributes();

// When the EventHandler expires, send StopLED directive to stop LED animation
// and end skill session.
return handlerInput.responseBuilder
    .addDirective(buildStopLEDDirective(sessionAttributes.endpointId))
    .withShouldEndSession(true)
    .speak(request.expirationPayload.data)
    .getResponse();
```