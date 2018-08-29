from Phidget22.PhidgetException import *
from Phidget22.Devices import *
from Phidget22.Devices.Manager import *
from Phidget22.Phidget import *

import sys

try:
    from pkg_resources import get_distribution, DistributionNotFound
    _dist = get_distribution('phidget_hello_world')
    # Normalize case for Windows systems
    dist_loc = os.path.normcase(_dist.location)
    here = os.path.normcase(__file__)
    if not here.startswith(os.path.join(dist_loc, 'phidget_hello_world')):
        # not installed, but there is another version that *is*
        raise DistributionNotFound
except (ImportError,DistributionNotFound):
    __version__ = None
else:
    __version__ = _dist.version


class PhidgetHelloWorld():
    '''
    PhidgetHelloWorld.

    Example Usage:

    dev = PhidgetHelloWorld()
    '''
    def __init__(self,
                 *args,
                 **kwargs):

        try:
            self._manager = Manager()
        except RuntimeError as e:
            print("Runtime Error " + e.details + ", Exiting...\n")

        try:
            #logging example, uncomment to generate a log file
            #manager.enableLogging(PhidgetLogLevel.PHIDGET_LOG_VERBOSE, "phidgetlog.log")
            self._manager.setOnAttachHandler(self._phidget_attached)
            self._manager.setOnDetachHandler(self._phidget_detached)
        except PhidgetException as e:
            self._local_error_catcher(e)

    def _local_error_catcher(e):
        print("Phidget Exception: " + str(e.code) + " - " + str(e.details) + ", Exiting...")
        raise RuntimeError

    def _phidget_attached(self,phidget,channel):
        serial_number = channel.getDeviceSerialNumber()
        device_name = channel.getDeviceName()
        print("Hello to Device " + str(device_name) + ", Serial Number: " + str(serial_number))

    def _phidget_detached(self,phidget,channel):
        serial_number = channel.getDeviceSerialNumber()
        device_name = channel.getDeviceName()
        print("Goodbye Device " + str(device_name) + ", Serial Number: " + str(serial_number))

    def open(self):
        print("Opening....")
        try:
           self._manager.open()
        except PhidgetException as e:
            self._local_error_catcher(e)

    def close(self):
        print("Closing...")
        try:
            self._manager.close()
        except PhidgetException as e:
            self._local_error_catcher(e)

def main():
    # try:
    dev = PhidgetHelloWorld()
    dev.open()
    print("Phidget Simple Playground (plug and unplug devices)");
    print("Press Enter to end anytime...");
    character = sys.stdin.read(1)
    #     dev.close()
    # except:
    #     print("Something bad happened!");
    #     exit(1)
    exit(0)
# -----------------------------------------------------------------------------------------
if __name__ == '__main__':

    main()
