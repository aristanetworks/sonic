
from ..core.component.i2c import I2cComponent
from ..core.pci import PciSwitch, DownstreamPciPort, UpstreamPciPort
from ..core.register import RegisterMap, Register, RegBitField, RegBitRange

from ..drivers.plx import PlxPex8700I2cDevDriver

class PlxPortDesc(object):
   VS0 = 0
   VS1 = 1
   def __init__(self, port=None, name=None, vs=VS0, upstream=False):
      self.port = port
      self.name = name
      self.station = port // 12
      self.lane = (port % 12) * 2
      self.vs = vs
      self.upstream = upstream

class DownstreamPlxPort(DownstreamPciPort):
   def __init__(self, *, desc, **kwargs):
      super(DownstreamPlxPort, self).__init__(port=desc.port, **kwargs)
      self.desc = desc

   @property
   def name(self):
      return self.desc.name

   def enable(self):
      return self.parent.enablePort(self)

   def disable(self):
      return self.parent.disablePort(self)

   def available(self):
      return self.parent.isPortAvailable(self)

class UpstreamPlxPort(UpstreamPciPort):
   def __init__(self, *, desc, **kwargs):
      super(UpstreamPlxPort, self).__init__(port=desc.port, **kwargs)
      self.desc = desc

   @property
   def name(self):
      return self.desc.name

   def enable(self):
      return self.parent.enablePort(self)

   def disable(self):
      return self.parent.disablePort(self)

class PlxPciSwitch(PciSwitch):

   UPSTREAM_PORT_CLS = UpstreamPlxPort
   DOWNSTREAM_PORT_CLS = DownstreamPlxPort

   def __init__(self, plx=None, ports=None, **kwargs):
      super(PlxPciSwitch, self).__init__(**kwargs)
      self.plx = plx
      self.ports = {}
      self.addPciPorts(ports)

   def addPciPorts(self, descs):
      self.descs = descs
      for desc in descs:
         if desc.upstream:
            p = self.upstreamPort(port=desc.port, desc=desc)
         else:
            p = self.downstreamPort(port=desc.port, device=desc.port, desc=desc)
         self.ports[p.name] = p

   def portByName(self, name):
      return self.ports[name]

   def busForPort(self, port):
      return super(PlxPciSwitch, self).busForPort(0)

   def enablePort(self, port):
      return self.plx.enablePort(port)

   def disablePort(self, port):
      return self.plx.disablePort(port)

   def isPortAvailable(self, port):
      # TODO: handle case where vs is not enabled
      return port.desc.vs == self.upstream.desc.vs

class Plx(I2cComponent):

   PLX_PORT_CONFIG = []

   def __init__(self, addr, reverse=False, **kwargs):
      super(Plx, self).__init__(addr=addr, **kwargs)
      self.reverse = reverse
      self.pci = None

   def enablePort(self, port):
      raise NotImplementedError

   def disablePort(self, port):
      raise NotImplementedError

   def addPciSwitch(self, parent, **kwargs):
      assert not self.pci
      self.pci = parent.newComponent(
         PlxPciSwitch,
         plx=self,
         **kwargs
      )
      return self.pci

class Plx8700RegisterMap(RegisterMap):
   SltCap = Register(0x7c,
      RegBitField(5, 'hotPlugSurprise', ro=False),
      RegBitField(6, 'hotPlugCapable', ro=False),
   )

   PortDisable = Register(0x208, name="portDisable")

   Vs0Upstream = Register(0x360,
      RegBitRange(0, 4, 'upstreamPort', ro=False),
      RegBitRange(8, 12, 'ntPort', ro=False),
      RegBitField(13, 'ntEnable', ro=False),
   )

   Vs0PortVec = Register(0x380, name="vs0PortVec")
   Vs1PortVec = Register(0x384, name="vs1PortVec")

class PlxPex8700(Plx):

   DRIVER = PlxPex8700I2cDevDriver
   REGISTER_CLS = Plx8700RegisterMap

   def enableHotPlug(self):
      self.driver.enableHotPlug()

   def disablePort(self, port):
      self.driver.disablePort(port.port)

   def enablePort(self, port):
      self.driver.enablePort(port.port)

   def setUpstreamPort(self, port):
      self.driver.setUpstreamPort(port.port)

   def setNtPort(self, port):
      self.driver.setNtPort(port.port)

   def enableNt(self, on=False):
      self.driver.enableNt(on)

   def smbusPing(self):
      return self.driver.smbusPing()

   def setupVs(self):
      if not self.pci.ports:
         return

      vs = [0, 0]
      for port in self.pci.ports.values():
         vs[port.desc.vs] |= 1 << port.port
      for i, v in enumerate(vs):
         self.vsPortVec(i, v)

   def vsPortVec(self, vsId, value=None):
      return self.driver.vsPortVec(vsId, value)
