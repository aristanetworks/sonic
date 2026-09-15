
from ..core.component import Priority
from ..core.pci import PciSwitch, DownstreamPciPort, UpstreamPciPort

from ..drivers.microsemi import MicrosemiDriver
from ..drivers.pci import PciSwitchPortDriver

class MicrosemiPortDesc(object):
   def __init__(self, port, dsp, partition, name=None, upstream=False):
      self.port = port
      self.dsp = dsp
      self.partition = partition
      self.name = name
      self.upstream = upstream

class DownstreamMicrosemiPort(DownstreamPciPort):

   DRIVER = PciSwitchPortDriver
   PRIORITY = Priority.DEFAULT

   def __init__(self, *, desc, **kwargs):
      super().__init__(port=desc.port, **kwargs)
      self.desc = desc

   @property
   def name(self):
      return self.desc.name

   def enable(self):
      self.driver.enable()

   def disable(self):
      self.driver.disable()

   def bind(self):
      return self.parent.enablePort(self)

   def unbind(self):
      return self.parent.disablePort(self)

   def available(self):
      return self.parent.isPortAvailable(self)

class UpstreamMicrosemiPort(UpstreamPciPort):

   def __init__(self, *, desc, addr=None, **kwargs):
      super().__init__(port=desc.port, addr=addr, **kwargs)
      self.desc = desc

   @property
   def name(self):
      return self.desc.name

   def enable(self):
      self.parent.enablePort(self)

   def disable(self):
      self.parent.disablePort(self)

class Microsemi(PciSwitch):

   DRIVER = MicrosemiDriver
   PRIORITY = Priority.DEFAULT

   UPSTREAM_PORT_CLS = UpstreamMicrosemiPort
   DOWNSTREAM_PORT_CLS = DownstreamMicrosemiPort

   def __init__(self, ports=None, **kwargs):
      super().__init__(**kwargs)
      self.ports = {}
      if ports:
         self.addPciPorts(ports)

   def addPciPorts(self, descs):
      for desc in descs:
         self.addPciPort(desc)

   def addPciPort(self, desc=None, **kwargs):
      if desc.upstream:
         assert desc.dsp == 0, "Upstream port should always have DSP=0"
         p = self.upstreamPort(port=desc.port, device=0, desc=desc, **kwargs)
      else:
         p = self.downstreamPort(port=desc.port, device=desc.dsp - 1, desc=desc, **kwargs)
      self.ports[p.name] = p
      return p

   def portByName(self, name):
      return self.ports[name]

   def isPortAvailable(self, port):
      return port.desc.partition == self.upstream.desc.partition

   def setupVs(self):
      for port in self.ports.values():
         desc = port.desc
         self.driver.bind(desc.port, desc.dsp, desc.partition)

   def enablePort(self, port):
      desc = port.desc
      return self.driver.bind(desc.port, desc.dsp, desc.partition)

   def disablePort(self, port, flags=0x2):
      desc = port.desc
      return self.driver.unbind(desc.dsp, desc.partition, flags=flags)

   def ping(self):
      try:
         return self.driver.ping()
      except Exception: # pylint: disable=broad-except
         return False
