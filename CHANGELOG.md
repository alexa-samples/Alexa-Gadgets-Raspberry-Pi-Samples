## ChangeLog

### [1.0.0] - 2019-08-15

* Initial release of the `Alexa Gadgets Raspberry Pi Samples`, a Python-based prototyping software for Raspberry Pi which enables quick creation of an Alexa Gadget using the [Alexa Gadgets Toolkit](https://developer.amazon.com/alexa/alexa-gadgets).

### [2.0.0] - 2019-12-10

* Added support for the sample apps to use Bluetooth Low Energy (BLE) transport mode to communicate with Echo device.
* Replaced `setup.sh` script with `launch.py` script as a single point of entry for configuring the gadget's credentials, installing dependencies, configuring the transport mode (Classic Bluetooth / BLE), and launching the example scripts.