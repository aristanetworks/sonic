
from __future__ import absolute_import, division, print_function

from ...core.card import Card, CardSlot
from ...core.config import Config
from ...core.domain import PowerDomain
from ...core.fabric import Fabric
from ...core.linecard import Linecard
from ...core.log import getLogger
from ...descs.led import LedColor
from ...libs.wait import waitFor

from ..eeprom import At24C512
from ..pca9541 import Pca9541
from ..plx import PlxPex8700

logging = getLogger(__name__)

class DenaliCard(Card):

   ASICS = []
   PLX_PORTS = []
   PLX_REGS = None

   def __init__(self, *args, **kwargs):
      self.scd = None
      self.pca = None
      self.eeprom = None
      self.plx = None
      self.asics = []
      self.gpio1 = None
      self.gpio2 = None
      super(DenaliCard, self).__init__(*args, **kwargs)

   def detach(self):
      if self.plx:
         self.slot.pci.detach(self.getUpstreamPort())
      super().detach()

   def getEeprom(self):
      try:
         return self.eeprom.prefdl()
      except Exception: # pylint: disable=broad-except
         logging.debug("%s: failed to read eeprom", self)
         return {}

   def getUpstreamPort(self):
      slotId = self.slot.parent.getSlotId()
      name = 'sup%d' % slotId if slotId != 0 else 'lcpu'
      return self.plx.pci.portByName(name)

   def createGpio1(self):
      self.gpio1 = None

   def createPlx(self, parent=None):
      self.plx = self.pca.newComponent(
         PlxPex8700,
         addr=self.pca.i2cAddr(0x38),
         registerCls=self.PLX_REGS,
      )
      self.plx.addPciSwitch(
         parent,
         ports=self.PLX_PORTS,
      )
      if self.PLX_PORTS:
         self.slot.pci.attach(self.getUpstreamPort())

   def createAsics(self):
      self.asics = []

   def createScd(self):
      self.scd = None

   def controlPlaneOn(self):
      return False

   def dataPlaneOn(self):
      return False

   def createStandbyDpm(self):
      '''Override in child classes if a linecard has a standby DPM.'''
      pass

   def standbyCommon(self):
      '''Define Mux, Prefdl eeprom, Gpio1, Dpm, Pols, Temp sensors,
         and Fans...
      '''
      self.standby = self.newComponent(PowerDomain)

      self.pca = self.standby.newComponent(Pca9541, addr=self.slot.bus.i2cAddr(0x77),
                                           driverMode='user')
      self.eeprom = self.pca.newComponent(At24C512, addr=self.pca.i2cAddr(0x50),
                                          label='card_%d' % self.slot.slotId)
      self.createGpio1()
      if self.gpio1 is not None:
         self.gpio1.addRedGreenGpioLed('status', 'statusRed', 'statusGreen')

   def standbyDomain(self):
      pass

   def mainDomain(self):
      pass

   def controlDomain(self):
      assert self.control is None
      assert self.main is None
      self.control = self.newComponent(PowerDomain, enabled=self.controlPlaneOn)
      self.main = self.newComponent(PowerDomain, enabled=self.dataPlaneOn)
      self.createStandbyDpm()
      self.createPlx(parent=self.main)

   def loadStandbyDomain(self):
      self.standbyCommon()
      self.standbyDomain()
      if self.isDetected():
         self.controlDomain()

   def loadMainDomain(self):
      self.createScd()
      self.createAsics()
      self.mainDomain()

   def createCpu(self):
      logging.error("cpu not declared for this card")

   def loadCpuDomain(self):
      self.createCpu()
      if self.cpu:
         assert self.slot, 'cpu needs to create a slot object'
         self.loadMainDomain()

   def powerStandbyDomainIs(self, on):
      raise NotImplementedError

   def powerControlDomainIs(self, on):
      raise NotImplementedError

   def powerLcpuIs(self, on, lcpuCtx):
      raise NotImplementedError

   def powerPremainPowerDomainIs(self, on):
      '''Enable Microsemi downstream port and Plx.'''
      assert self.gpio1, "gpio1 is not created yet."
      if on:
         assert self.poweredOn(), "Card is not turned on."
         self.gpio1.pcieReset(False)
         waitFor(self.plx.smbusPing, "Can't take Plx out of reset.")
         self.setupPlx()
         self.enablePlxPcieUpstreamLink(True)
         self.getInventory().getLed('status').setColor(LedColor.AMBER)
      else:
         self.enablePlxPcieUpstreamLink(False)
         self.gpio1.pcieReset(True)
         self.getInventory().getLed('status').setColor(LedColor.OFF)

   def powerMainPowerDomainIs(self, on):
      if on:
         for asicId, asic in enumerate(self.asics):
            logging.debug('Taking asic %d on card %s out of reset', asicId, self)
            asic.resetIn()
            waitFor(asic.isInReset, "Can't have asic in reset")
            asic.resetOut()
            logging.debug('Asic %d on card %s is out of reset', asicId, self)
      else:
         for asicId, asic in enumerate(self.asics):
            logging.debug('Putting asic %d on card %s in reset', asicId, self)
            asic.resetIn()
            waitFor(asic.isInReset, "Can't have asic in reset")
            logging.debug('Asic %d on card %s is in reset', asicId, self)

      if on:
         self.slot.enablePciPort()
         # Verify asic presence
         for asicId, asic in enumerate(self.asics):
            # TODO: fixme pci addr does not exists
            self.asics[asicId].waitForIt()

   def powerOnIs(self, on, lcpuCtx=None):
      if on:
         # Make sure the port is disabled before we start. If it isn't we risk
         # triggering bogus PCI state that will result in kernel lockups later.
         self.slot.disablePciPort()
         self.powerStandbyDomainIs(True)
         self.powerControlDomainIs(True)
         self.powerPremainPowerDomainIs(True)
         if lcpuCtx:
            self.powerLcpuIs(True, lcpuCtx)
         else:
            self.powerMainPowerDomainIs(True)
         self.slot.enablePciPort()
      else:
         self.slot.disablePciPort()
         # NOTE: Wait for linux to be done processing pci hotplug events
         #       not waiting would lead to uncorrectable pci errors with a high
         #       risk of softlockups
         waitFor(lambda: not self.getUpstreamPort().reachable(),
                 timeout=Config().power_off_linecard_wait_pci_timeout)
         if lcpuCtx:
            self.powerLcpuIs(False, lcpuCtx)
         else:
            self.powerMainPowerDomainIs(False)
         self.powerPremainPowerDomainIs(False)
         self.powerControlDomainIs(False)
         self.powerStandbyDomainIs(False)

   def poweredOn(self):
      if self.runningOnLcpu():
         return True
      if self.gpio1 is None:
         # Linecard is likely unsupported or not loaded
         return False
      try:
         return self.gpio1.powerGood()
      except Exception:  # pylint: disable=broad-except
         logging.debug('%s: failed to read power good', self)
         return False

   def enablePlxPcieUpstreamLink(self, bind):
      upstream = self.getUpstreamPort()
      upstream.disable()
      if bind:
         self.slot.pci.bind()
         upstream.enable()
      else:
         self.slot.pci.unbind()

   def setupPlx(self):
      self.plx.enableHotPlug()
      self.plx.setUpstreamPort(self.getUpstreamPort())
      self.plx.enableNt(False)

   def setupIdentification(self):
      self.pca.takeOwnership()
      self.pca.setup()
      self.eeprom.setup()

class DenaliCardSlot(CardSlot):

   CARD_CLS = None

   def __init__(self, parent, slotId, pci, bus, presenceGpio=None,
                presenceChangedGpio=None, card=None):
      super(DenaliCardSlot, self).__init__(parent, slotId)
      self.pci = pci
      self.bus = bus
      self.card = card
      self.presenceGpio = presenceGpio
      self.presenceChangedGpio = presenceChangedGpio
      if not self.card:
         self.loadCard(self.CARD_CLS(self))

   def getPresence(self):
      if self.presenceGpio is None:
         return self.card.pca.ping()

      return self.presenceGpio.isActive()

   def getPresenceChanged(self):
      if self.presenceChangedGpio is None:
         return None

      ret = self.presenceChangedGpio.isActive()
      if ret:
         self.presenceChangedGpio.setActive(True)
      return ret

   def getEeprom(self):
      if not self.getPresence():
         return None
      self.card.setupIdentification()
      return self.card.eeprom.prefdl()

class DenaliLinecardBase(DenaliCard, Linecard):
   pass

class DenaliFabricBase(DenaliCard, Fabric):
   pass

class DenaliLinecardSlot(DenaliCardSlot):
   CARD_CLS = DenaliLinecardBase

class DenaliFabricSlot(DenaliCardSlot):
   CARD_CLS = DenaliFabricBase
