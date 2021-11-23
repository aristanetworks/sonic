
from __future__ import absolute_import, division, print_function

import time

from ...core.log import getLogger
from ...core.platform import getSysEeprom
from ...core.provision import ProvisionConfig, ProvisionMode
from ...core.register import Register, RegisterMap, RegBitField, SetClearRegister
from ...core.types import PciAddr
from ...core.utils import getCmdlineDict

from ...drivers.pca9555 import GpioRegister
from ...drivers.scd.register import (
   ScdResetRegister,
   ScdSramRegister,
   ScdStatusChangedRegister,
)
from ...drivers.scd.sram import SramContent

from ...libs.wait import waitFor

from ..plx import PlxPex8700
from ..scd import Scd

from .card import DenaliLinecardBase, DenaliLinecardSlot

logging = getLogger(__name__)

class DenaliLinecard(DenaliLinecardBase):
   PLATFORM = None

   SCD_PCI_OFFSET = 0
   ASICS = []

   PLX_LCPU_MODE = None

   def createPlx(self):
      self.plx = self.pca.newComponent(PlxPex8700, addr=self.pca.i2cAddr(0x38))

   def createScd(self):
      scdAddr = self.slot.pciAddr(bus=self.SCD_PCI_OFFSET)
      self.scd = self.main.newComponent(Scd, scdAddr, registerCls=ScdRegisterMap)

   def createAsics(self):
      self.asics = []
      for desc in self.ASICS:
         addr = self.slot.pciAddr(bus=desc.bus)
         # TODO: use sysfs entries for the asic resets
         rst = getattr(self.scd.regs, 'je%dReset' % desc.rstIdx)
         prst = getattr(self.scd.regs, 'je%dPcieReset' % desc.rstIdx)
         # TODO: avoid the rescan on the lcpu side, look into plx vs hotswap
         asic = self.main.newComponent(desc.cls, addr, rescan=True,
                                       resetGpio=rst, pcieResetGpio=prst)
         self.asics.append(asic)

   def createCpu(self):
      assert self.CPU_CLS
      slotId = int(getCmdlineDict().get('slot_id', 0))
      self.slot = DenaliLinecardSlot(self, slotId, PciAddr(bus=0x04), None,
                                     card=self)
      self.cpu = self.newComponent(self.CPU_CLS, self.slot)
      self.eeprom = getSysEeprom()

   def waitForStandbyPowerOn(self):
      try:
         if not self.pca.ping():
            return False
         self.pca.takeOwnership()
         if not self.gpio1.powerCycle() and self.gpio1.standbyPowerGood():
            return True
      except IOError:
         pass
      return False

   def powerStandbyDomainOn(self, cycle=False):
      if not self.gpio1.standbyPowerGood() or cycle:
         logging.debug('%s: power cycling standby', self)
         self.gpio1.powerCycle(True)
         waitFor(self.waitForStandbyPowerOn, "standby power good")

      self.gpio1.cpEcbOn(True)
      time.sleep(0.2)
      self.gpio1.dpEcbOn(True)
      time.sleep(0.1)
      self.gpio1.scdReset(False)
      self.gpio1.pcieUpstream(False)
      waitFor(self.poweredOn, "card to turn on",
              wait=2000, interval=100)

   def powerStandbyDomainOff(self):
      self.gpio1.dpEcbOn(False)
      self.gpio1.cpEcbOn(False)
      self.gpio1.scdReset(True)
      self.gpio1.pcieUpstream(True)
      waitFor(lambda: (not self.poweredOn()), "card to turn off")

   def powerStandbyDomainIs(self, on):
      '''Turn on card Ecbs. On Denali linecard, we expect
         Dpms will then be turned on as well as Pols by hardware. So no need to
         do anything with Dpm. When all is done, power good is asserted.'''
      assert self.gpio1, "gpio1 is not created yet."
      if on:
         for i in range(3):
            try:
               self.powerStandbyDomainOn(cycle=i > 0)
               return
            except Exception: # pylint: broad-except
               logging.exception('%s: issue when trying to power on', self)
      else:
         try:
            self.powerStandbyDomainOff()
            return
         except Exception: # pylint: broad-except
            logging.exception('%s: issue when trying to power off', self)

   def populateSramFromPrefdl(self):
      sramContent = SramContent()
      prefdlRaw = self.eeprom.readPrefdlRaw()
      for addr, byte in enumerate(prefdlRaw):
         if not sramContent.write(addr, byte):
            logging.error('%s: Could not write further content to the SRAM', self)
            break
      try:
         self.syscpld.sram(sramContent)
      except IOError:
         logging.error('Failed to populate linecard SRAM content FPGA image likely '
                       'outdated')
         raise

   def provisionIs(self, provisionStatus):
      config = ProvisionConfig(self.slot.slotId)
      if provisionStatus is None:
         provisionStatus = config.loadMode()
      else:
         config.writeMode(provisionStatus)
      self.syscpld.provision(provisionStatus)

   def powerLcpuIs(self, on, lcpuCtx):
      if on:
         assert self.syscpld.lcpuInReset(), "LCPU should be in reset"
         self.gpio1.lcpuMode(True)
         self.syscpld.slotId(self.slot.slotId)
         self.provisionIs(lcpuCtx.provision)
         self.populateSramFromPrefdl()
         self.syscpld.gmacLowPower(False)
         # At high temp, toggling GMAC too soon after low power might prevent it from
         # coming up
         time.sleep(0.1)
         self.syscpld.supGmacReset(False)
         self.syscpld.lcpuGmacReset(False)
         self.syscpld.lcpuDisableSet(False)
         self.syscpld.lcpuResetSet(False)
         waitFor(self.syscpld.lcpuPowerGood, "LCPU power to be good",
                 interval=50)
         # This is rather ugly, but seems to be necessary to avoid any issues with
         # the tg3 driver for the SUP GMAC. With a shorter sleep, or no sleep at all
         # we sometimes experience TX transmit timeouts during the lifetime of the
         # linecard. This sleep seems to completely remove this issue. Time will tell
         # if it's a real fix for that, but so far looks necessary. Sleeping 4
         # seconds or more also seem to not show up the tg3_abort_hw timed out error
         # at power on time.
         #
         # Unfortunately for now I can't think of a better fix than sleep. I don't
         # think we can wait on anything...
         time.sleep(4)
      else:
         self.syscpld.lcpuResetSet(True)
         self.syscpld.lcpuDisableSet(True)
         self.syscpld.lcpuGmacReset(True)
         self.syscpld.supGmacReset(True)
         self.syscpld.gmacLowPower(True)
         self.syscpld.provision(ProvisionMode.NONE)
         self.syscpld.slotId(0)
         self.gpio1.lcpuMode(False)
         waitFor(lambda: (not self.syscpld.lcpuPowerGood()),
                 "LCPU power to be turned off", interval=50)

   def setupPlxLcpuMode(self):
      if self.PLX_LCPU_MODE:
         self.plx.vsPortVec(0, self.PLX_LCPU_MODE[0])
         self.plx.vsPortVec(1, self.PLX_LCPU_MODE[1])

   def setupPlx(self):
      super(DenaliLinecard, self).setupPlx()
      self.setupPlxLcpuMode()

class GpioRegisterMap(RegisterMap):
   BANK0 = GpioRegister(0x0,
      RegBitField(1, 'standbyPowerGood', ro=True),
      RegBitField(1, 'tempAlert', flip=True),
      RegBitField(2, 'powerGood'),
      RegBitField(4, 'powerCycle', ro=False),
      RegBitField(7, 'pcieFatalError', flip=True),
   )
   BANK1 = GpioRegister(0x1,
      RegBitField(0, 'cpEcbOn', ro=False),
      RegBitField(1, 'dpEcbOn', ro=False),
      RegBitField(2, 'statusGreen', ro=False, flip=True),
      RegBitField(3, 'statusRed', ro=False, flip=True),
      RegBitField(4, 'pcieUpstream', ro=False),
      RegBitField(5, 'lcpuMode', ro=False),
      RegBitField(6, 'pcieReset', ro=False, flip=True),
      RegBitField(7, 'scdReset', ro=False, flip=True),
   )

class ScdRegisterMap(RegisterMap):
   RESET0 = ScdResetRegister(0x4000,
      RegBitField(0, 'je0Reset', ro=False),
      RegBitField(1, 'je0PcieReset', ro=False),
      RegBitField(2, 'je1Reset', ro=False),
      RegBitField(3, 'je1PcieReset', ro=False),
      RegBitField(4, 'je2Reset', ro=False),
      RegBitField(5, 'je2PcieReset', ro=False),
   )

class StandbyScdRegisterMap(RegisterMap):
   REVISION = Register(0x01, name='revision')
   SCRATCHPAD = Register(0x02, name='scratchpad', ro=False)
   SLOT_ID = Register(0x03, name='slotId', ro=False)
   STATUS0 = ScdStatusChangedRegister(0x04,
      RegBitField(0, name='lcpuPowerGood'),
      RegBitField(2, name='lcpuInReset'),
      RegBitField(3, name='lcpuMuxSel', flip=True),
   )
   STATUS1 = ScdStatusChangedRegister(0x06,
      RegBitField(6, name='vrmAlert'),
      RegBitField(7, name='vrmHot'),
   )
   STATUS2 = ScdStatusChangedRegister(0x05,
      RegBitField(0, name='lcpuThermTrip'),
      RegBitField(1, name='lcpuHot'),
      RegBitField(2, name='lcpuAlert'),
   )
   STATUS7 = ScdStatusChangedRegister(0x12,
      RegBitField(3, name='lcpuPresent'),
   )
   LCPU_CTRL = SetClearRegister(0x30, 0x31,
      RegBitField(0, name='lcpuDisableSet', ro=False),
      RegBitField(1, name='lcpuResetSet', ro=False),
      RegBitField(3, name='supGmacReset', ro=False),
      RegBitField(4, name='lcpuGmacReset', ro=False),
      RegBitField(5, name='gmacLowPower', ro=False),
   )
   PROVISION = Register(0x32, name='provision', ro=False)
   SRAM = ScdSramRegister(0x33, name='sram')
