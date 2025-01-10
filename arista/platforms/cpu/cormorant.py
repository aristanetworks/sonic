from ...core.cpu import Cpu
from ...core.pci import PciRoot

from ...components.cpu.amd.k10temp import K10Temp
from ...components.cpu.cormorant import (
   CormorantCpldRegisters,
   CormorantSysCpld,
)

from ...components.dpm.adm1266 import Adm1266, AdmCause
from ...components.max6658 import Max6658
from ...components.scd import Scd

from ...descs.sensor import Position, SensorDesc

class CormorantCpu(Cpu):

   PLATFORM = 'cormorant'

   def __init__(self, cpldRegisterCls=CormorantCpldRegisters, **kwargs):
      super(CormorantCpu, self).__init__(**kwargs)

      self.pciRoot = self.newComponent(PciRoot)
      port = self.pciRoot.rootPort(device=0x18, func=3)
      port.newComponent(K10Temp, addr=port.addr, sensors=[
         SensorDesc(diode=0, name='CPU',
                    position=Position.OTHER, target=70, overheat=95, critical=115),
      ])

      port = self.pciRoot.rootPort(device=0x18, func=7)
      cpld = port.newComponent(Scd, addr=port.addr)
      self.cpld = cpld

      cpld.createInterrupt(addr=0x3000, num=0)

      cpld.addSmbusMasterRange(0x8000, 2, 0x80, 4)
      cpld.newComponent(Max6658, addr=cpld.i2cAddr(0, 0x4c), sensors=[
         SensorDesc(diode=0, name='CPU board',
                    position=Position.OTHER, target=55, overheat=75, critical=85),
         SensorDesc(diode=1, name='Back-panel',
                    position=Position.OUTLET, target=55, overheat=75, critical=85),
      ])

      self.addFanGroup(
         slots=self.parent.CHASSIS.FAN_SLOTS, count=self.parent.CHASSIS.FAN_COUNT
      )
      cpld.addFanSlotBlock(
         slotCount=self.parent.CHASSIS.FAN_SLOTS,
         fanCount=self.parent.CHASSIS.FAN_COUNT,
      )

      self.syscpld = self.newComponent(CormorantSysCpld, addr=cpld.i2cAddr(4, 0x23),
                                       registerCls=cpldRegisterCls)

   def addCpuDpm(self, addr=None, causes=None):
      """
      The ADM1266 DPM logs a snapshot of GPI_[6:2] as EVENT_[4:0],
      Unlike Lorikeet, these causes are not one-hot encoded
      """
      addr = addr or self.cpuDpmAddr()
      gpioMask = 0b000111110
      return self.cpld.newComponent(Adm1266, addr=addr, causes=causes or [
         AdmCause(0x11 << 1, AdmCause.NOFANS, mask=gpioMask),
         AdmCause(0x12 << 1, AdmCause.REBOOT, mask=gpioMask),
         AdmCause(0x13 << 1, AdmCause.CPU_OVERTEMP, mask=gpioMask),
         AdmCause(0x14 << 1, AdmCause.OVERTEMP, mask=gpioMask),
         AdmCause(0x15 << 1, AdmCause.POWERLOSS, mask=gpioMask),
         AdmCause(0x16 << 1, AdmCause.CPU, mask=gpioMask),
      ])

   def cpuDpmAddr(self, addr=0x4f, t=3, **kwargs):
      return self.cpld.i2cAddr(1, addr, t=t, **kwargs)

   # in the case of quartz, oliveville found at 0x11
   def switchDpmAddr(self, addr=0x11, t=3, **kwargs):
      return self.cpld.i2cAddr(5, addr, t=t, **kwargs)

   def addFanGroup(self, slots=3, count=2):
      self.cpld.addFanGroup(0x9000, 3, slots, count)

   def getPciPort(self, num):
      device, func = {
         0: (0x01, 1),
         1: (0x03, 5),
         2: (0x01, 4),
      }[num]
      bridge = self.pciRoot.pciBridge(device=device, func=func)
      return bridge.downstreamPort(port=0)
