
import os

from .component.component import Component
from .component.pci import PciComponent
from .types import SysfsPath
from .utils import inSimulation

from ..libs.wait import waitForPath

class PciNotReady(Exception):
   pass

class PciSysfsPath(SysfsPath): # pylint: disable=abstract-method
   pass

class RootPciAddr(PciSysfsPath):
   def __init__(self, parent=None, device=0, func=0):
      self.parent = parent
      self.device = device
      self.func = func

   @property
   def upstream(self):
      return self.parent

   @property
   def domain(self):
      return self.upstream.domain

   @property
   def bus(self):
      return self.upstream.bus

   def __str__(self):
      return '%04x:%02x:%02x.%d' % (self.domain, self.bus, self.device, self.func)

   def getSysfsPath(self):
      return os.path.join(self.upstream.parent.getSysfsPath(), str(self))

class DownstreamPciAddr(PciSysfsPath):
   def __init__(self, port=None, device=0, func=0):
      self.port = port
      self.device = device
      self.func = func

   @property
   def parent(self):
      return self.port.parent

   @property
   def upstream(self):
      return self.port.upstream

   @property
   def domain(self):
      return self.upstream.addr.domain

   @property
   def bus(self):
      return self.port.bus

   def __str__(self):
      try:
         return '%04x:%02x:%02x.%d' % (self.domain, self.bus, self.device, self.func)
      except PciNotReady:
         return '----:--:%02x.%d' % (self.device, self.func)

   def getSysfsPath(self):
      return os.path.join(self.upstream.addr.getSysfsPath(), str(self))

class UpstreamPciAddr(DownstreamPciAddr):
   @property
   def bus(self):
      return self.upstream.downstreamBus

   def __str__(self):
      if not self.upstream:
         return '----:--:%02x.%d' % (self.device, self.func)
      return super(UpstreamPciAddr, self).__str__()

   def getSysfsPath(self):
      if not self.upstream:
         return os.path.join('/sys/bus/pci/devices', str(self))
      return super(UpstreamPciAddr, self).getSysfsPath()

class PciPort(PciComponent):

   ADDR_CLS = None
   CHILD_PORT_CLS = None

   def __init__(self, port=0, upstream=None, **kwargs):
      super(PciPort, self).__init__(**kwargs)
      self.upstream_ = upstream
      self.secondary_ = None
      self.subordinate_ = None
      self.port = port
      self.ports = {}
      self.addrs = {}

   def attach(self, port):
      self.ports[port.addr] = port
      port.upstream_ = self

   def detach(self, port):
      del self.ports[port.addr]
      port.upstream_ = None

   @property
   def bus(self):
      return self.upstream.downstreamBus

   @property
   def upstream(self):
      return self.upstream_

   @property
   def downstreamBus(self):
      return self.secondary

   @property
   def secondary(self):
      # NOTE: reading this attribute ends up reading the sysfs every time
      #       it is wasteful but necessary to deal with corner cases.
      #       the file could not exist or be erroneous if read to early.
      self.secondary_ = self.readSecondaryBus()
      return self.secondary_

   @property
   def subordinate(self):
      # NOTE: reading this attribute ends up reading the sysfs every time
      #       it is wasteful but necessary to deal with corner cases.
      #       the file could not exist or be erroneous if read to early.
      self.subordinate_ = self.readSubordinateBus()
      return self.subordinate_

   def readSecondaryBus(self):
      if inSimulation():
         return 1
      try:
         return self.readSysfs('secondary_bus_number')
      except FileNotFoundError as e:
         raise PciNotReady from e

   def readSubordinateBus(self):
      if inSimulation():
         return 255
      try:
         return self.readSysfs('subordinate_bus_number')
      except FileNotFoundError as e:
         raise PciNotReady from e

   def readSysfs(self, entry, wait=False):
      path = os.path.join(self.addr.getSysfsPath(), entry)

      if wait:
         waitForPath(path, timeout=5, interval=100,
                     description='waiting for pci port ready')

      value = None
      while not value:
         with open(path, encoding='utf8') as f:
            value = f.read()
      return int(value, 0)

   def enable(self):
      pass

   def disable(self):
      pass

   def available(self):
      return True

   def reachable(self):
      if not self.upstream.reachable():
         return False
      return os.path.exists(self.addr.getSysfsPath())

   def pciAddr(self, device=0, func=0):
      addr = self.addrs.get((device, func))
      if addr is None:
         addr = self.ADDR_CLS(port=self, device=device, func=func)
         self.addrs[(device, func)] = addr
      return addr

   def pciEndpoint(self, cls=None, device=0, func=0, **kwargs):
      cls = cls or UpstreamPciPort
      addr = self.pciAddr(device=device, func=func)
      p = self.ports.get(addr)
      if p is not None:
         assert isinstance(p, cls)
         return p
      p = self.newComponent(
         cls,
         addr=addr,
         upstream=self,
         **kwargs
      )
      addr.port = p
      self.ports[addr] = p
      return p

class DownstreamPciPort(PciPort):

   ADDR_CLS = DownstreamPciAddr

   @property
   def upstream(self):
      return self.parent.upstream

class UpstreamPciPort(PciPort):

   ADDR_CLS = UpstreamPciAddr

class RootPciPort(UpstreamPciPort):

   ADDR_CLS = UpstreamPciAddr

   @property
   def bus(self):
      return self.parent.bus

   @property
   def domain(self):
      return self.parent.domain

   @property
   def upstream(self):
      return self.parent

class PciBridge(PciComponent):

   UPSTREAM_ADDR_CLS = UpstreamPciAddr
   DOWNSTREAM_ADDR_CLS = DownstreamPciAddr
   UPSTREAM_PORT_CLS = UpstreamPciPort
   DOWNSTREAM_PORT_CLS = DownstreamPciPort

   def __init__(self, **kwargs):
      super(PciBridge, self).__init__(**kwargs)
      self.upstreamPorts = {}
      self.downstreamPorts = {}

   @property
   def upstream(self):
      return next(iter(self.upstreamPorts.values()))

   def busForPort(self, port):
      absBus = self.upstream.secondary + port
      assert absBus <= self.upstream.subordinate
      return absBus

   def upstreamPort(self, port=0, device=0, func=0, **kwargs):
      p = self.upstreamPorts.get(port)
      if p is None:
         addr = self.UPSTREAM_ADDR_CLS(port=None, device=device, func=func)
         p = self.newComponent(
            self.UPSTREAM_PORT_CLS,
            addr=addr,
            **kwargs,
         )
         addr.port = p
         self.upstreamPorts[port] = p
      return p

   def downstreamPort(self, port=0, device=0, func=0, **kwargs):
      p = self.downstreamPorts.get(port)
      if p is None:
         addr = self.DOWNSTREAM_ADDR_CLS(port=None, device=device, func=func)
         p = self.newComponent(
            self.DOWNSTREAM_PORT_CLS,
            addr=addr,
            **kwargs
         )
         addr.port = p
         self.downstreamPorts[port] = p
      return p

class PciSwitch(PciBridge):
   pass

class RootPciBridge(Component):

   ADDR_CLS = RootPciAddr
   PORT_CLS = RootPciPort
   BRIDGE_CLS = PciBridge

   def __init__(self, domain=0, bus=0, **kwargs):
      super(RootPciBridge, self).__init__(**kwargs)
      self.domain = domain
      self.bus = bus
      self.addrs = {}
      self.ports = {}
      self.bridges = {}

   @property
   def downstreamBus(self):
      return self.bus

   def pciAddr(self, device=0, func=0):
      key = (device, func)
      addr = self.addrs.get(key)
      if addr is None:
         addr = self.ADDR_CLS(parent=self, device=device, func=func)
         self.addrs[key] = addr
      return addr

   def pciPort(self, device=0, func=0):
      addr = self.pciAddr(device=device, func=func)
      port = self.ports.get(addr)
      if port is None:
         port = self.newComponent(
            self.PORT_CLS,
            addr=addr,
         )
         addr.parent = port
         self.ports[addr] = port
      addr.parent = port
      return port

   def pciBridge(self, device=0, func=0):
      port = self.pciPort(device=device, func=func)
      bridge = self.bridges.get(port)
      if bridge is None:
         bridge = self.newComponent(
            self.BRIDGE_CLS,
            port=port,
         )
         self.bridges[port] = bridge
         bridge.upstreamPorts[port] = port
      return bridge

   def reachable(self):
      return True

   def __str__(self):
      return 'pci%04x:%02x' % (self.domain, self.bus)

   def getSysfsPath(self):
      return os.path.join('/sys/devices', str(self))

class PciRoot(Component):
   def __init__(self, **kwargs):
      super(PciRoot, self).__init__(**kwargs)
      self.roots = {}

   def getRoot(self, domain, bus):
      key = (domain, bus)
      root = self.roots.get(key)
      if root is None:
         root = self.newComponent(
            RootPciBridge,
            domain=domain,
            bus=bus,
         )
         self.roots[key] = root
      return root

   def rootPort(self, domain=0, bus=0, device=0, func=0):
      return self.getRoot(domain, bus).pciPort(device, func)

   def pciAddr(self, domain=0, bus=0, device=0, func=0):
      return self.getRoot(domain, bus).pciAddr(device, func)

   def pciBridge(self, domain=0, bus=0, device=0, func=0):
      return self.getRoot(domain, bus).pciBridge(device, func)
