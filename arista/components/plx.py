
from collections import namedtuple

from ..core.component.i2c import I2cComponent
from ..core.register import RegisterMap, Register, RegBitField, RegBitRange

from ..drivers.plx import PlxPex8700I2cDevDriver

PlxPortDesc = namedtuple('PlxPortDesc', [
   'port',
   'lane',
   'name',
])

class PlxPort(object):
   def __init__(self, plx, pciePort, pcieLane, name):
      self.plx = plx
      self.pciePort = pciePort
      self.pcieLane = pcieLane
      self.name = name

   def enable(self):
      return self.plx.enablePort(self)

   def disable(self):
      return self.plx.disablePort(self)

class Plx(I2cComponent):
   def __init__(self, addr, reverse=False, **kwargs):
      super(Plx, self).__init__(addr=addr, **kwargs)
      self.ports = []
      self.reverse = reverse

   def addPorts(self, ports):
      for port in ports:
         self.ports.append(PlxPort(self, port.port, port.lane, port.name))

   def get(self, name):
      port = [p for p in self.ports if p.name == name]
      if len(port) != 1:
         return None
      return port[0]

   def enablePort(self, port):
      raise NotImplementedError

   def disablePort(self, port):
      raise NotImplementedError

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

   def disableUpstreamPort(self, port, off=True):
      self.driver.disableUpstreamPort(port, off)

   def setUpstreamPort(self, port=0):
      self.driver.setUpstreamPort(port)

   def setNtPort(self, port=2):
      self.driver.setNtPort(port)

   def enableNt(self, on=False):
      self.driver.enableNt(on)

   def smbusPing(self):
      return self.driver.smbusPing()

   def vsPortVec(self, vsId, value=None):
      return self.driver.vsPortVec(vsId, value)
