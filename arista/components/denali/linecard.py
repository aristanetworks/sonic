
from __future__ import absolute_import, division, print_function

import time

from ...core.log import getLogger
from ...core.platform import getSysEeprom
from ...core.provision import ProvisionConfig, ProvisionMode
from ...core.register import Register, RegisterMap, RegBitField, SetClearRegister

from ...drivers.pca9555 import GpioRegister
from ...drivers.scd.register import (
   ScdResetRegister,
   ScdSramRegister,
   ScdStatusChangedRegister,
)
from ...drivers.scd.sram import SramContent

from ...libs.wait import waitFor
from ...libs.rebootfs import setOsSoftwareRebootCause

from ...utils.rpc.helper import getGlobalRpcClient

from ..plx import Plx8700RegisterMap
from ..scd import Scd

from .card import DenaliLinecardBase, DenaliLinecardSlot

logging = getLogger(__name__)

class LinecardPlx8700Registers(Plx8700RegisterMap):
   GpioLow = Register(0x61c,
      RegBitField(0, 'hasScdSeuError'),
   )

class DenaliLinecard(DenaliLinecardBase):
   PLATFORM = None

   SCD_PCI_OFFSET = 0
   ASICS = []
   PLX_PORTS = []
   PLX_REGS = LinecardPlx8700Registers

   def createScd(self):
      downstream = self.plx.pci.portByName('scd')
      upstream = downstream.pciEndpoint()
      self.scd = upstream.newComponent(
         Scd,
         addr=upstream.addr,
         registerCls=ScdRegisterMap,
      )

   def createAsics(self):
      self.asics = []
      for desc in self.ASICS:
         downstream = self.plx.pci.portByName('je%d' % desc.asicId)
         # TODO: avoid the rescan on the lcpu side, look into plx vs hotswap
         # TODO: attach pcie reset signal to a PciEndpoint object
         upstream = downstream.pciEndpoint()
         asic = upstream.newComponent(
            desc.cls,
            addr=upstream.addr,
            rescan=True,
            coreResets=[self.scd.regs.getGpio('je%dReset' % desc.rstIdx)],
            pcieResets=[self.scd.regs.getGpio('je%dPcieReset' % desc.rstIdx)],
         )
         self.asics.append(asic)

   def createCpu(self):
      assert self.CPU_CLS
      self.cpu = self.newComponent(self.CPU_CLS)
      self.slot = self.cpu.createCardSlot(DenaliLinecardSlot, self)
      self.pca = self.slot.bus
      self.createPlx(parent=self)
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

   def standbyDomain(self):
      self.slot.parent.getCookies().addLinecard(self)

   def controlPlaneOn(self):
      return self.gpio1.cpEcbOn()

   def dataPlaneOn(self):
      return self.gpio1.dpEcbOn()

   def powerStandbyDomainOn(self, cycle=False):
      if not self.gpio1.standbyPowerGood() or cycle:
         logging.debug('%s: power cycling standby', self)
         self.gpio1.powerCycle(True)
         waitFor(self.waitForStandbyPowerOn, "standby power good")

   def powerStandbyDomainOff(self):
      pass

   def powerControlDomainOn(self):
      self.gpio1.cpEcbOn(True)
      time.sleep(0.2)
      self.gpio1.dpEcbOn(True)
      time.sleep(0.1)
      self.gpio1.scdReset(False)
      self.gpio1.pcieUpstream(False)
      waitFor(self.poweredOn, "card to turn on",
              wait=2000, interval=100)

   def powerControlDomainOff(self):
      self.gpio1.dpEcbOn(False)
      self.gpio1.cpEcbOn(False)
      self.gpio1.scdReset(True)
      self.gpio1.pcieUpstream(True)
      waitFor(lambda: (not self.poweredOn()), "card to turn off")

   def powerStandbyDomainIs(self, on):
      assert self.gpio1, "gpio1 is not created yet."
      if on:
         for i in range(3):
            try:
               self.powerStandbyDomainOn(cycle=i > 0)
               return
            except Exception: # pylint: disable=broad-except
               logging.exception('%s: failed to power standby on', self)
      else:
         try:
            self.powerStandbyDomainOff()
            return
         except Exception: # pylint: disable=broad-except
            logging.exception('%s: failed to power standby off', self)

   def powerControlDomainIs(self, on):
      '''Turn on card Ecbs. On Denali linecard, we expect
         Dpms will then be turned on as well as Pols by hardware. So no need to
         do anything with Dpm. When all is done, power good is asserted.'''
      if on:
         try:
            self.powerControlDomainOn()
         except Exception: # pylint: disable=broad-except
            logging.exception('%s: failed to power control plane on', self)
      else:
         try:
            self.powerControlDomainOff()
         except Exception: # pylint: disable=broad-except
            logging.exception('%s: failed to power control plane off', self)

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
      self.plx.setupVs()

   def setupPlx(self):
      super(DenaliLinecard, self).setupPlx()
      self.setupPlxLcpuMode()

   def getLastPostCode(self):
      if self.syscpld.lcpuPresent():
         return self.syscpld.lastPostCode()
      return None

   def hasNextPostCodeAvail(self):
      if self.syscpld.lcpuPresent():
         return self.syscpld.nextPostCodeAvailable()
      return False

   def handleUngracefulReboot(self):
      supervisorClient = getGlobalRpcClient(platform=self)
      response = supervisorClient.getRebootCause()

      if response and response.get('reboot_cause') != 'None':
         setOsSoftwareRebootCause(response['reboot_cause'])

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
   STATUS6 = ScdResetRegister(0x10,
      RegBitField(7, name='lcScdWatchdogStopAllTraffic'),
      RegBitField(6, name='lcScdWatchdogInterrupt'),
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
   LAST_POST_CODE = Register(0x80, name='lastPostCode')
   NEXT_POST_CODE_AVAIL = Register(0x84,
      RegBitField(0, name='nextPostCodeAvailable', flip=True),
   )
   NEXT_POST_CODE = Register(0x85, name='nextPostCode')
