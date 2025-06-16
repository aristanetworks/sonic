
from ...core.psu import PsuSlot
from ...core.supervisor import Supervisor

from ...descs.gpio import GpioDesc

from ...libs.rebootfs import getOsSoftwareRebootCause, setAllLcRebootInfo

from ..eeprom import At24C64
from ..microsemi import Microsemi
from ..pca9541 import Pca9541
from ..psu.artesyn import Art700
from ..psu.delta import ECD3000M
from ..scd import Scd

from .card import (
   DenaliLinecardBase,
   DenaliLinecardSlot,
   DenaliFabricBase,
   DenaliFabricSlot,
)

class DenaliSupervisor(Supervisor):
   LINECARD_PORTS = []
   FABRIC_PORTS = []
   PSUS = []

   def __init__(self, pciSwitchCls=Microsemi, **kwargs):
      super(DenaliSupervisor, self).__init__(**kwargs)

      self.chassisEeproms = []

      self.pciSwitch = None
      self.pciSwitchCls = pciSwitchCls

      self.linecardCount = len(self.LINECARD_PORTS)
      self.fabricCount = len(self.FABRIC_PORTS)

      self.linecardSmbus = range(0, self.linecardCount)
      self.fabricSmbus = range(self.linecardCount,
                               self.linecardCount + self.fabricCount)

      self.scd = None

      self.createScd()
      self.createPciSwitch()
      self.createLinecards()
      self.createFabricCards()
      self.createPsus()

   def createScd(self):
      port = self.cpu.pciRoot.rootPort(device=0x1c).pciEndpoint(port=0)
      self.scd = port.newComponent(Scd, addr=port.addr)
      port.parent = self.scd # FIXME
      self.scd.addSmbusMasterRange(0x8000, 3, 0x80)
      self.scd.addUartPortRange(0x7e00, self.linecardCount)

      self.scd.createWatchdog()

      self.scd.addGpios([
         GpioDesc("supervisor_want_active", 0x5000, 0),
         GpioDesc("supervisor_active", 0x5000, 1, ro=True),
         GpioDesc("supervisor_slotid", 0x5000, 2, ro=True),
         GpioDesc("peer_supervisor_present", 0x5000, 3, ro=True),
         GpioDesc("heartbeat_in", 0x5000, 4, ro=True),
         GpioDesc("heartbeat_out", 0x5000, 5),
      ])

      self.chassisEeproms = [
         self.scd.newComponent(At24C64, addr=self.scd.i2cAddr(14, 0x51),
                               label='chassis1'),
         self.scd.newComponent(At24C64, addr=self.scd.i2cAddr(15, 0x51),
                               label='chassis2'),
      ]

   def createPciSwitch(self):
      port = self.cpu.pciRoot.rootPort(device=0x03)
      uport = port.pciEndpoint(func=1)
      self.pciSwitch = uport.newComponent(
         self.pciSwitchCls,
         addr=uport.addr,
      )
      port.attach(self.pciSwitch.upstreamPort())

   def createLinecards(self):
      for lcId in range(self.linecardCount):
         name = "lc%d" % (lcId + 1)
         slotId = lcId + DenaliLinecardBase.ABSOLUTE_CARD_OFFSET
         self.scd.addGpios([
            GpioDesc("%s_present" % name, 0x4100, lcId, ro=True),
            GpioDesc("%s_present_changed" % name, 0x4100, 16 + lcId),
         ])
         pci = self.pciSwitch.addPciPort(self.LINECARD_PORTS[lcId])
         bus = self.scd.getSmbus(self.linecardSmbus[lcId])
         presenceGpio = self.scd.inventory.getGpio("%s_present" % name)
         slot = DenaliLinecardSlot(self, slotId, pci, bus, presenceGpio=presenceGpio)
         self.linecardSlots.append(slot)

   def createFabricCards(self):
      self.fabricSmbus = range(8, 8 + 6)
      self.fabricSlots = []

      for fcId in range(self.fabricCount):
         name = "fc%d" % (fcId + 1)
         slotId = fcId + DenaliFabricBase.ABSOLUTE_CARD_OFFSET
         self.scd.addGpios([
            GpioDesc("%s_present" % name, 0x4110, fcId, ro=True),
            GpioDesc("%s_present_changed" % name, 0x4110, 16 + fcId),
         ])
         pci = self.pciSwitch.addPciPort(self.FABRIC_PORTS[fcId])
         bus = self.scd.getSmbus(self.fabricSmbus[fcId])
         presenceGpio = self.scd.inventory.getGpio("%s_present" % name)
         self.fabricSlots.append(DenaliFabricSlot(self, slotId, pci, bus,
                                                  presenceGpio=presenceGpio))

   def createPsus(self):
      for idx, desc in enumerate(self.PSUS):
         name = "psu%d" % desc.psuId
         # NOTE: Otterlake has a gap of 1 between banks. The gpio creation might
         #       have to become shim specific in the future.
         bit = idx if desc.bank == 1 else idx + 1
         self.scd.addGpios([
            GpioDesc("%s_present" % name, 0x5080, bit, ro=True),
            GpioDesc("%s_present_changed" % name, 0x5080, 16 + bit),
            GpioDesc("%s_ok" % name, 0x5090, bit, ro=True),
            GpioDesc("%s_ok_changed" % name, 0x5090, 16 + bit),
            GpioDesc("%s_ac_a_ok" % name, 0x50A0, bit, ro=True),
            GpioDesc("%s_ac_a_ok_changed" % name, 0x50A0, 16 + bit),
            GpioDesc("%s_ac_b_ok" % name, 0x50B0, bit, ro=True),
            GpioDesc("%s_ac_b_ok_changed" % name, 0x50B0, 16 + bit),
         ])
         pca = self.scd.newComponent(
            Pca9541,
            addr=self.scd.i2cAddr(desc.bus, desc.addr),
            driverMode='kernel',
         )
         slot = pca.newComponent(
            PsuSlot,
            slotId=desc.psuId,
            desc=desc,
            addrFunc=pca.i2cAddr,
            presentGpio=self.scd.inventory.getGpio('%s_present' % name),
            inputOkGpio=self.scd.inventory.getGpio('%s_ok' % name),
            outputOkGpio=[
               self.scd.inventory.getGpio('%s_ac_a_ok' % name),
               self.scd.inventory.getGpio('%s_ac_b_ok' % name),
            ],
            psus=[
               ECD3000M,
               Art700,
            ],
         )
         self.psuSlots.append(slot)

   def readSlotId(self):
      return 2 if self.scd.inventory.getGpio('supervisor_slotid').isActive() else 1

   def handleUngracefulReboot(self):
      rebootCause = getOsSoftwareRebootCause()
      ungracefulRebootCause = (
         'Heartbeat with the Supervisor card lost'
         if 'Kernel Panic' in rebootCause
         else 'None'
      )
      setAllLcRebootInfo(self.getChassis(), ungracefulRebootCause)
