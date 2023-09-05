from collections import OrderedDict

from ..config import Config
from ..inventory import Inventory

DEFAULT_WAIT_TIMEOUT = 15

class Priority(object):
   DEFAULT = 0
   THERMAL = 0
   COOLING = 0
   BACKGROUND = 1
   DPM = 1
   POWER = 1
   LED = 1

   def priorityFilter(*priorities):
      return staticmethod(lambda component: component.priority in priorities)

   defaultFilter = priorityFilter(DEFAULT)
   backgroundFilter = priorityFilter(BACKGROUND)

class Component(object):

   QUIRKS = None

   def __init__(self, addr=None, priority=Priority.DEFAULT, drivers=None,
                inventoryCls=None, inventory=None, parent=None, quirks=None,
                **kwargs):
      super(Component, self).__init__()
      self.components = []
      self.addr = addr
      self.priority = priority
      self.drivers = OrderedDict()
      self.inventory = inventory
      self.parent = parent
      self.quirks = quirks or self.QUIRKS or []
      self.label = None
      if not inventory and inventoryCls:
         self.inventory = inventoryCls()
      self.addDrivers(drivers)
      self.__dict__.update(kwargs)

   def __str__(self):
      attrs = ['addr']
      kwargs = ['%s=%s' % (k, v) for k, v in self.__dict__.items()
                if k in attrs and v is not None]
      return '%s(%s)' % (self.__class__.__name__, ', '.join(kwargs))

   def __repr__(self):
      return f'<{self}>'

   def isEnabled(self):
      return True

   def addComponent(self, component):
      assert isinstance(component, Component)
      component.priority = max(component.priority, self.priority)
      self.components.append(component)
      return self

   def newComponent(self, cls, *args, **kwargs):
      # TODO: do not create inventory objects for components that don't need it
      #       also consider LazyInventory as an alternative
      inventory = Inventory()
      component = cls(inventory=inventory, *args, parent=self, **kwargs)
      self.addComponent(component)
      return component

   def iterComponents(self, filters=Priority.defaultFilter, recursive=True):
      if filters is None:
         filters = []
      if not hasattr(filters, '__iter__'):
         filters = [filters]
      allFilters = lambda x: all(f(x) for f in filters)

      for component in filter(allFilters, self.components):
         if not component.isEnabled():
            continue

         yield component
         if recursive:
            for sub in component.iterComponents(filters):
               yield sub

   def iterInventory(self, filters=None):
      for component in self.iterComponents(filters=filters):
         yield component.inventory
      yield self.inventory

   def addDrivers(self, drivers):
      if drivers:
         for drv in drivers:
            key = getattr(drv, 'module', drv.__class__.__name__)
            if key not in self.drivers:
               self.drivers[key] = drv

   def getInventory(self):
      return self.inventory

   def setup(self):
      for driver in self.drivers.values():
         driver.setup()
      for driver in self.drivers.values():
         driver.finish()

   def finish(self, filters=Priority.defaultFilter):
      # underlying component are initialized recursively but require the parent to
      # be fully initialized
      for component in self.iterComponents(filters, recursive=False):
         component.setup()
      for component in self.iterComponents(recursive=False):
         component.finish(filters)

   def refresh(self):
      for component in self.components:
         component.refresh()
      for driver in self.drivers.values():
         driver.refresh()

   def clean(self):
      for component in self.components:
         component.clean()
      for driver in reversed(self.drivers.values()):
         driver.clean()

   def resetIn(self):
      for component in self.components:
         component.resetIn()
      for driver in reversed(self.drivers.values()):
         driver.resetIn()

   def resetOut(self):
      for driver in self.drivers.values():
         driver.resetOut()
      for component in self.components:
         component.resetOut()

   def waitForIt(self, timeout=DEFAULT_WAIT_TIMEOUT):
      for component in self.components:
         component.waitForIt(timeout)

   def __diag__(self, ctx):
      return {}

   def __try_diag__(self, ctx):
      try:
         return self.__diag__(ctx)
      except Exception: # pylint: disable=broad-except
         if not ctx.safe:
            raise
         return {}

   def genDiag(self, ctx):
      output = {
         "version": 2,
         "classes": [c.__name__ for c in self.__class__.__mro__[:-1]],
         "name": str(self),
         "data": self.__try_diag__(ctx),
         "drivers": [d.genDiag(ctx) for d in self.drivers.values()],
         "components": [],
         "inventory": None,
      }

      if isinstance(self.inventory, Inventory) and \
         self.inventory not in ctx.inventories:
         try:
            output["inventory"] = self.inventory.__diag__(ctx)
         except Exception: # pylint: disable=broad-except
            if not ctx.safe:
               raise
         ctx.inventories.add(self.inventory)

      if ctx.recursive:
         output["components"] = [c.genDiag(ctx) for c in
                         self.iterComponents(filters=None, recursive=False)]
      return output

class PciComponent(Component):
   # XXX: Legacy, use component.pci.PciComponent instead
   def __init__(self, **kwargs):
      super(PciComponent, self).__init__(**kwargs)
