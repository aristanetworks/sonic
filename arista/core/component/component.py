
from ..config import Config
from . import Component as LegacyComponent
from . import Priority

from ..log import getLogger

logging = getLogger(__name__)

class Component(LegacyComponent):

   DRIVER = None
   PRIORITY = Priority.DEFAULT
   REGISTER_CLS = None

   def __init__(self, *args, **kwargs):
      # HACK: some refactor is required to get rid of this
      #       the addr is not always provided as a kwarg
      if args and 'addr' not in kwargs:
         kwargs['addr'] = args[0]
         args = args[1:]
      attrs = [
         # FIXME: workaround until DriverSelector
         ('driverCls', self.DRIVER),
         ('priority', self.PRIORITY),
         ('registerCls', self.REGISTER_CLS),
      ]
      for key, default in attrs:
         kwargs[key] = kwargs.get(key) or default
      driverCls = kwargs.get('driverCls')
      drivers = [
         driverCls(**kwargs), # pylint: disable=not-callable
      ] if driverCls else []
      # TODO: cleanup the parent dependency when possible
      super(Component, self).__init__(
         *args,
         drivers=drivers,
         **kwargs
      )
      assert len(self.drivers) <= 1, "New style components can only have one driver"
      self.driver = next(iter(self.drivers.values())) if self.drivers else None
      # FIXME: This is required until metainventory is in place
      #        we need to refresh the hardware thresholds of the temp sensors once
      #        the component is initialized, however this can only work on the temp
      #        sensors of the current components. Until metainventory is enabled, we
      #        need to store a local collection per component that stores only its
      #        own temp sensors
      self._tempSensorsWorkaround = []
      self.addObjects(**kwargs)

   def addObjects(self, fans=None, leds=None, sensors=None, rails=None, **kwargs):
      for sensor in sensors or []:
         self.addTempSensor(sensor)
      for fan in fans or []:
         self.addFan(fan)
      for led in leds or []:
         self.addLed(led)
      for rail in rails or []:
         self.addRail(rail)

   def addFan(self, desc, **kwargs):
      return self.inventory.addFan(self.driver.getFan(desc, **kwargs))

   def addFans(self, descs, **kwargs):
      return [self.addFan(desc, **kwargs) for desc in descs]

   def addFanLed(self, desc, **kwargs):
      return self.inventory.addLed(self.driver.getFanLed(desc, **kwargs))

   def addFanLeds(self, descs, **kwargs):
      return [self.addFanLed(desc, **kwargs) for desc in descs]

   def addLed(self, desc, **kwargs):
      return self.inventory.addLed(self.driver.getLed(desc, **kwargs))

   def addLeds(self, descs, **kwargs):
      return [self.addLed(desc, **kwargs) for desc in descs]

   def addTempSensor(self, desc, **kwargs):
      ts = self.inventory.addTemp(self.driver.getTempSensor(desc, **kwargs))
      self._tempSensorsWorkaround.append(ts)
      return ts

   def addTempSensors(self, descs, **kwargs):
      return [self.addTempSensor(desc, **kwargs) for desc in descs]

   def addReset(self, desc, **kwargs):
      return self.inventory.addReset(self.driver.getReset(desc, **kwargs))

   def addResets(self, descs, **kwargs):
      return [self.addReset(desc, **kwargs) for desc in descs]

   def addGpio(self, desc, **kwargs):
      return self.inventory.addGpio(self.driver.getGpio(desc, **kwargs))

   def addGpios(self, descs, **kwargs):
      return [self.addGpio(desc, **kwargs) for desc in descs]

   def addRail(self, desc, **kwargs):
      return self.inventory.addRail(self.driver.getRail(desc, **kwargs))

   def addRails(self, descs, **kwargs):
      return [self.addRail(desc, **kwargs) for desc in descs]

   def addPowerCycle(self, desc, **kwargs):
      powerCycle = self.driver.getPowerCycle(desc, **kwargs)
      return self.inventory.addPowerCycle(powerCycle)

   def finish(self, filters=Priority.defaultFilter):
      super(Component, self).finish(filters=filters)
      if Config().write_hw_thresholds:
         for ts in self._tempSensorsWorkaround:
            try:
               ts.refreshHardwareThresholds()
            except Exception: # pylint: disable=broad-except
               logging.exception("%s: failed to refresh hardware thresholds for %s"
                                 % (self, ts))

   def applyQuirks(self, delayed=False):
      for quirk in self.quirks:
         if quirk.DELAYED == delayed:
            logging.info('%s: quirk: %s', self, quirk)
            quirk.run(self)
