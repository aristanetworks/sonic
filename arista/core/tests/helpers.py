from ..fixed import FixedSystem
from ..linecard import Linecard
from ..platform_loader import platform_loader
from ..supervisor import Supervisor

def _getFixedSystemClasses(ignoreSupervisor=False):
   for platformCls in platform_loader.all_platforms():
      if ignoreSupervisor and issubclass(platformCls, Supervisor):
         continue
      # NOTE: this leaves behind the following products
      # - chassis
      # - fabric cards
      # - linecards without CPUs
      if issubclass(platformCls, Linecard) and platformCls.CPU_CLS:
         yield platformCls
      elif issubclass(platformCls, FixedSystem):
         yield platformCls

def getAllFixedSystems(ignoreSupervisor=False):
   for platformCls in _getFixedSystemClasses(ignoreSupervisor=ignoreSupervisor):
      yield platformCls()

def getAllFixedSystemClasses(ignoreSupervisor=False):
   yield from _getFixedSystemClasses(ignoreSupervisor=ignoreSupervisor)

def getAllFixedSystemKeys(ignoreSupervisor=False):
   for platformCls in _getFixedSystemClasses(ignoreSupervisor=ignoreSupervisor):
      yield platformCls.SID[0] if platformCls.SID else platformCls.SKU[0]

getAllSystems = getAllFixedSystems
getAllSystemClasses = getAllFixedSystemClasses
getAllSystemKeys = getAllFixedSystemKeys

def classname(obj):
   if isinstance(obj, type):
      return obj.__name__
   return obj.__class__.__name__

def isChildComponentOf(component, parent):
   while parent:
      if component in parent.components:
         return True
      parent = parent.parent
   return False

def isAncestorToComponent(component, ancestor):
   while component:
      if component == ancestor:
         return True
      component = component.parent
   return False

def getPlatformSkus():
   return {sku: pc for pc in platform_loader.all_platforms() for sku in pc.SKU}
