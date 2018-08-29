from Phidget22.PhidgetException import *
from Phidget22.Phidget import *
from Phidget22.Net import *
from Phidget22.Devices.Stepper import *
from Phidget22.Devices.DigitalInput import *
from Phidget22.Devices.VoltageRatioInput import *
from Phidget22.Devices.Log import *
from Phidget22.LogLevel import *

import os
import yaml
from threading import Timer
import time
from datetime import datetime

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


DEBUG = False

class Latch():
    '''
    Latch.
    '''
    _CONTROL_MODE_STEP = 0
    _CONTROL_MODE_RUN = 1
    _HOME_SWITCH_ACTIVE = 0
    _POSITION_EPSILON = 2

    def __init__(self,*args,**kwargs):
        self._homed = False
        self._released_handler = None

    def set_stepper(self,stepper):
        self.stepper = stepper
        self.stepper.setOnStoppedHandler(self._stopped_handler)

    def set_home_switch(self,home_switch):
        self.home_switch = home_switch
        self.home_switch.setOnStateChangeHandler(self._home_switch_handler)

    def set_released_handler(self,released_handler):
        self._released_handler = released_handler

    def _all_attached(self):
        if not self.stepper.getAttached():
            return False
        if not self.home_switch.getAttached():
            return False
        return True

    def _stopped_handler(self,phidget):
        if self._at_release_position():
            if self._released_handler is not None:
                self._released_handler()

    def _at_home_position(self):
        position = self.stepper.getPosition()
        if abs(position) < self._POSITION_EPSILON:
            return True
        return False

    def _at_close_position(self):
        position = self.stepper.getPosition()
        if abs(position - self.stepper.configuration['close_position']) < self._POSITION_EPSILON:
            return True
        return False

    def _at_release_position(self):
        position = self.stepper.getPosition()
        if abs(position - self.stepper.configuration['release_position']) < self._POSITION_EPSILON:
            return True
        return False

    def _home_switch_handler(self,phidget,state):
        if state == self._HOME_SWITCH_ACTIVE:
            self._finish_homing()

    def _finish_homing(self):
        if not self._all_attached():
            return
        self.stop()
        self.stepper.setControlMode(self._CONTROL_MODE_STEP)
        self._zero()
        self.stepper.setVelocityLimit(self.stepper.configuration['velocity_limit'])
        self._homed = True
        if self._released_handler is not None:
            self._released_handler()

    def _zero(self):
        offset = self.stepper.getPosition()
        self.stepper.addPositionOffset(-offset)
        self.stepper.setTargetPosition(0)

    def home(self):
        if not self._all_attached():
            print("not all attached!")
            return
        if self.home_switch_active():
            self._finish_homing()
            self.stepper.setEngaged(True)
            return
        self.stepper.setEngaged(False)
        self._homed = False
        self.stepper.setControlMode(self._CONTROL_MODE_RUN)
        self.stepper.setVelocityLimit(self.stepper.configuration['home_velocity'])
        self.stepper.setEngaged(True)

    def homed(self):
        return self._homed

    def stop(self):
        self.stepper.setVelocityLimit(0)

    def close(self):
        if self.homed():
            if not self._at_close_position():
                self.stepper.setTargetPosition(self.stepper.configuration['close_position'])

    def release(self):
        if self.homed():
            if not self._at_release_position():
                self.stepper.setTargetPosition(self.stepper.configuration['release_position'])
        else:
            self.home()

    def home_switch_active(self):
        return self.home_switch.getState() == self._HOME_SWITCH_ACTIVE

    def released(self):
        if self._at_release_position():
            return True
        return False



class PhidgetHelloWorld():
    '''
    PhidgetHelloWorld.

    Example Usage:

    configuration_path = '/media/usb0/configuration.yaml'
    dev = PhidgetHelloWorld(configuration_path)
    '''

    _HEAD_BAR_SWITCH_ACTIVE = 1
    _RELEASE_SWITCH_ACTIVE = 1
    _SETUP_PERIOD = 1.0
    _HEAD_BAR_SWITCH_RESET_DELAY = 2.0

    def __init__(self,
                 configuration_path,
                 *args,
                 **kwargs):
        self._initialized = False
        if 'debug' in kwargs:
            self.debug = kwargs['debug']
        else:
            self.debug = DEBUG
        try:
            self._latches_enabled = kwargs['latches_enabled']
        except KeyError:
            self._latches_enabled = True

        with open(configuration_path) as f:
            configuration_yaml = f.read()

        configuration = yaml.load(configuration_yaml)

        try:
            log_base_directory = os.path.expanduser('~/logs')
            log_directory = os.path.join(log_base_directory,self._get_date_time_str())
            os.makedirs(log_directory)
            log_path = os.path.join(log_directory,'log.txt')
            Log.enable(LogLevel.PHIDGET_LOG_INFO,log_path)
        except PhidgetException as e:
            print("Phidget Exception %i: %s" % (e.code, e.details))

        self._phidgets = {}
        for name, phidget_configuration in configuration['phidgets'].items():
            if (phidget_configuration['channel_class'] == 'DigitalInput'):
                self._phidgets.update({name : DigitalInput()})
                self._phidgets[name].setIsHubPortDevice(True)
            elif (phidget_configuration['channel_class'] == 'Stepper'):
                self._phidgets.update({name : Stepper()})
            elif (phidget_configuration['channel_class'] == 'VoltageRatioInput'):
                self._phidgets.update({name : VoltageRatioInput()})
            else:
                break
            self._phidgets[name].name = name
            self._phidgets[name].configuration = phidget_configuration
            self._phidgets[name].setDeviceSerialNumber(phidget_configuration['device_serial_number'])
            self._phidgets[name].setHubPort(phidget_configuration['hub_port'])
            self._phidgets[name].setChannel(phidget_configuration['channel'])
            self._phidgets[name].setOnAttachHandler(self._phidget_attached)
            self._phidgets[name].open()

        self.right_head_latch = Latch()
        self.right_head_latch.set_stepper(self._phidgets['right_head_latch_motor'])
        self.right_head_latch.set_home_switch(self._phidgets['right_head_latch_home_switch'])
        self.right_head_latch.set_released_handler(self._latches_released_handler)

        self.left_head_latch = Latch()
        self.left_head_latch.set_stepper(self._phidgets['left_head_latch_motor'])
        self.left_head_latch.set_home_switch(self._phidgets['left_head_latch_home_switch'])
        self.left_head_latch.set_released_handler(self._latches_released_handler)

        self._phidgets['head_bar_switch'].setOnStateChangeHandler(self._head_bar_switch_handler)
        self._phidgets['release_switch'].setOnStateChangeHandler(self._release_switch_handler)

        self._phidgets['floor_force_sensor'].setOnVoltageRatioChangeHandler(self._floor_force_sensor_handler)

        self._setup_timer = Timer(self._SETUP_PERIOD,self._setup)
        # self._setup_timer.start()

        self._initialized = True

    def _phidget_attached(self,phidget):
        if phidget.configuration['channel_class'] == 'Stepper':
            self._debug_print()
            phidget.setEngaged(False)
            phidget.setAcceleration(phidget.configuration['acceleration'])
            self._debug_print(phidget.name,' acceleration: ',phidget.getAcceleration())
            phidget.setCurrentLimit(phidget.configuration['current_limit'])
            self._debug_print(phidget.name,' current_limit: ',phidget.getCurrentLimit())
            phidget.setHoldingCurrentLimit(phidget.configuration['holding_current_limit'])
            self._debug_print(phidget.name,' holding_current_limit: ',phidget.getHoldingCurrentLimit())
            phidget.setVelocityLimit(phidget.configuration['velocity_limit'])
            self._debug_print(phidget.name,' velocity_limit: ',phidget.getVelocityLimit())
        elif phidget.configuration['channel_class'] == 'VoltageRatioInput':
            phidget.setBridgeGain(phidget.configuration['bridge_gain'])
            self._debug_print('bridge_gain: ', phidget.getBridgeGain())
            phidget.setDataInterval(phidget.configuration['data_interval'])
            self._debug_print('data_interval: ', phidget.getDataInterval())
            phidget.setVoltageRatioChangeTrigger(phidget.configuration['voltage_ratio_change_trigger'])
            self._debug_print('voltage_ratio_change_trigger: ', phidget.getVoltageRatioChangeTrigger())
        elif phidget.configuration['channel_class'] == 'DigitalInput':
            pass

    def _all_attached(self):
        for phidget in self._phidgets.values():
            if not phidget.getAttached():
                self._debug_print(phidget.name,' not attached!')
                return False
        return True

    def _debug_print(self, *args):
        if self.debug:
            print(*args)

    def _get_date_time_str(self,timestamp=None):
        if timestamp is None:
            d = datetime.fromtimestamp(time.time())
        elif timestamp == 0:
            date_time_str = 'NULL'
            return date_time_str
        else:
            d = datetime.fromtimestamp(timestamp)
        date_time_str = d.strftime('%Y-%m-%d-%H-%M-%S')
        return date_time_str

    def _setup(self):
        self._debug_print('setup timer expired.')
        if self._initialized and self._all_attached():
            self._debug_print('setup!')
            self.home_latches()
        else:
            self._setup_timer = Timer(self._SETUP_PERIOD,self._setup)
            self._setup_timer.start()

    def _dummy_switch_handler(self,phidget,state):
        pass

    def _head_bar_switch_handler(self,phidget,state):
        if state == self._HEAD_BAR_SWITCH_ACTIVE:
            print('head bar switch activated')
            self._debug_print('head bar switch activated')
            self.close_latches()

    def _release_switch_handler(self,phidget,state):
        if state == self._HEAD_BAR_SWITCH_ACTIVE:
            self._debug_print('release switch activated')
            self.release_latches()

    def _floor_force_sensor_handler(self,phidget,voltage_ratio):
        print('voltage ratio: ',voltage_ratio)

    def _latches_released(self):
        return self.right_head_latch.released() and self.left_head_latch.released()

    def _latches_released_handler(self):
        if self._latches_released():
            self._debug_print('both latches released')
            self._head_bar_switch_reset_timer = Timer(self._HEAD_BAR_SWITCH_RESET_DELAY,self._reset_head_bar_switch_handler)
            self._head_bar_switch_reset_timer.start()

    def _reset_head_bar_switch_handler(self):
        self._phidgets['head_bar_switch'].setOnStateChangeHandler(self._head_bar_switch_handler)

    def enable_latches(self):
        self._latches_enabled = True

    def disable_latches(self):
        self._latches_enabled = False

    def home_latches(self):
        if not self._latches_enabled:
            return
        self._phidgets['head_bar_switch'].setOnStateChangeHandler(self._head_bar_switch_handler)
        self.right_head_latch.home()
        self.left_head_latch.home()

    def close_latches(self):
        if not self._latches_enabled:
            return
        self._phidgets['head_bar_switch'].setOnStateChangeHandler(self._dummy_switch_handler)
        self.right_head_latch.close()
        self.left_head_latch.close()

    def release_latches(self):
        if not self._latches_enabled:
            return
        if self.right_head_latch.homed() and self.left_head_latch.homed():
            self._phidgets['head_bar_switch'].setOnStateChangeHandler(self._dummy_switch_handler)
        self.right_head_latch.release()
        self.left_head_latch.release()


# -----------------------------------------------------------------------------------------
if __name__ == '__main__':

    debug = False
    latches_enabled = True
    dev = PhidgetHelloWorld(debug=debug,
                                 latches_enabled=latches_enabled)
