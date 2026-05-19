import os

from ...core import utils
from ...core.config import Config
from ...core.i2c_utils import I2cMsg
from ...core.log import getLogger

from ...core.driver.kernel.pci import PciKernelDriver
from ...core.driver.kernel.sysfs import (
   FanSysfsImpl,
   GpioSysfsImpl,
   LedLegacySysfsImpl,
   LedMonoSysfsImpl,
   LedMultiColorSysfsImpl,
   ResetSysfsImpl,
)

from ...core.driver.user.i2c import I2cDevDriver

from ...descs.led import LedKind

from ...libs.i2c import i2cBusFromName

logging = getLogger(__name__)

SCD_WAIT_TIMEOUT = 5.
SYS_SCD_PATH = '/sys/class/scd'

class ScdKernelDriver(PciKernelDriver):
   def __init__(self, scd=None, **kwargs):
      self.scd = scd
      super(ScdKernelDriver, self).__init__(module='scd-hwmon', **kwargs)

   def __str__(self):
      return '%s(addr=%s)' % (self.__class__.__name__, self.addr)

   def writeComponents(self, components, filename):
      PAGE_SIZE = 4096
      data = []
      data_size = 0

      for entry in components:
         entry_size = len(entry) + 1
         if entry_size + data_size > PAGE_SIZE:
            utils.writeConfig(self.addr.getSysfsPath(), {filename: '\n'.join(data)})
            data_size = 0
            data = []
         data.append(entry)
         data_size += entry_size

      if data:
         utils.writeConfig(self.addr.getSysfsPath(), {filename: '\n'.join(data)})

   def waitReadySim(self):
      logging.info('Waiting SCD %s.', os.path.join(self.addr.getSysfsPath(),
                                                   'smbus_tweaks'))
      logging.info('Done.')

   @utils.simulateWith(waitReadySim)
   def waitReady(self):
      path = os.path.join(self.addr.getSysfsPath(), 'smbus_tweaks')
      utils.FileWaiter(path, SCD_WAIT_TIMEOUT).waitFileReady()

   def getMasterNameForBus(self, bus):
      bpm = next(iter(self.scd.smbusMasters.values()))['bus']
      return self.getMasterName(bus // bpm, bus % bpm)

   def getMasterName(self, master, bus):
      return "SCD %s SMBus master %d bus %d" % (self.addr, master, bus)

   def refresh(self):
      # reload i2c bus cache
      masterName = self.getMasterName(0, 0)
      if not utils.inSimulation():
         self.scd.i2cOffset = i2cBusFromName(masterName, force=True)
      else:
         self.scd.i2cOffset = 2

   def setup(self):
      super(ScdKernelDriver, self).setup()

      scd = self.scd
      data = []

      for addr, info in scd.smbusMasters.items():
         data += ["smbus_master %#x %d %d" % (addr, info['id'], info['bus'])]

      for addr, info in scd.mdioMasters.items():
         data += ["mdio_master %#x %d %d %d" % (addr, info['id'], info['bus'],
                                                info['speed'])]

      for mdio in scd.mdios:
         data += ["mdio_device %d %d %d %d %d %d" % \
                  (mdio.master, mdio.bus, mdio.id, mdio.portAddr, mdio.deviceAddr, \
                   mdio.clause)]

      for addr, info in scd.uartPorts.items():
         data += ["uart %#x %d" % (addr, info['id'])]

      for addr, platform, slots, count in scd.fanGroups:
         data += ["fan_group %#x %u %u %u" % (addr, platform, slots, count)]

      if scd.ledFlashCtrlAddr is not None or scd.ledPaletteAddr is not None:
         flashAddr = scd.ledFlashCtrlAddr or 0
         paletteAddr = scd.ledPaletteAddr or 0
         data += ["led_ctrl %#x %#x" % (flashAddr, paletteAddr)]

      for desc in scd.leds:
         kind = getattr(desc, 'kind', LedKind.LEGACY)
         data += ["led %#x %s %s" % (desc.addr, desc.name, kind)]

      for addr, xcvrId in scd.osfps:
         data += ["osfp %#x %u" % (addr, xcvrId)]

      for addr, xcvrId in scd.qsfps:
         data += ["qsfp %#x %u" % (addr, xcvrId)]

      for addr, xcvrId in scd.sfps:
         data += ["sfp %#x %u" % (addr, xcvrId)]

      for reset in scd.resets:
         data += ["reset %#x %s %u" % (reset.addr, reset.name, reset.bit)]

      for gpio in scd.gpios:
         data += ["gpio %#x %s %u %d %d" % (gpio.addr, gpio.name, gpio.bit,
                                            int(gpio.ro), int(gpio.activeLow))]

      self.waitReady()

      logging.debug('creating scd objects')
      self.writeComponents(data, "new_object")

      if scd.msiRearmOffset:
         path = self.addr.getSysfsPath()
         utils.writeConfig(path, {'msi_rearm_offset': '%d' % scd.msiRearmOffset})
      for intrReg in scd.interrupts:
         intrReg.setup()

      self.refresh() # sync with kernel runtime state

      tweaks = []
      for tweak in scd.tweaks.values():
         tweaks += ["%#x %#x %#x %#x %#x %#x" % (
            tweak.addr.bus, tweak.addr.address, tweak.t, tweak.datr, tweak.datw,
            tweak.ed)]

      if tweaks:
         logging.debug('applying scd tweaks')
         self.writeComponents(tweaks, "smbus_tweaks")

   def finish(self):
      logging.debug('applying scd configuration')
      path = self.addr.getSysfsPath()
      # Configure NMI before triggering init
      if self.scd.nmiConfig is not None:
         self.scd.nmiConfig.setup(self.scd)
      if Config().lock_scd_conf:
         utils.writeConfig(path, {'init_trigger': '1'})
      # Disable kernel panicking on NMI interrupts
      utils.writeConfig(SYS_SCD_PATH, {
         'disable_nmi': '1',
         'watchdog_panic_enabled': '0',
      })
      super(ScdKernelDriver, self).finish()

   def resetSim(self, value):
      resets = [reset.getName() for reset in self.scd.getResets(autoOnly=True)]
      logging.debug('resetting devices %s', resets)

   @utils.simulateWith(resetSim)
   def reset(self, value):
      for reset in self.scd.getResets(autoOnly=True):
         if value:
            reset.resetIn()
         else:
            reset.resetOut()

   def resetIn(self):
      self.reset(True)

   def resetOut(self):
      self.reset(False)

   # FIXME: remove below methods once this driver has been reparented

   def getFan(self, desc):
      return FanSysfsImpl(self, desc)

   def getFanLed(self, desc):
      return self._getLed(desc)

   def getReset(self, desc, **kwargs):
      return ResetSysfsImpl(self, desc, **kwargs)

   def getGpio(self, desc, **kwargs):
      return GpioSysfsImpl(self, desc, hwActiveLow=True, **kwargs)

   def getLed(self, desc, **kwargs):
      return self._getLed(desc, **kwargs)

   def _getLed(self, desc):
      kind = getattr(desc, 'kind', LedKind.LEGACY)
      if kind == LedKind.LEGACY:
         return LedLegacySysfsImpl(self, desc)
      if kind == LedKind.BLUE:
         return LedMonoSysfsImpl(self, desc)
      return LedMultiColorSysfsImpl(self, desc)

class ScdI2cDevDriver(I2cDevDriver):
   def __init__(self, **kwargs):
      super(ScdI2cDevDriver, self).__init__(**kwargs)
      self.msgBus_ = None

   @property
   def msgBus(self):
      if not self.msgBus_:
         self.msgBus_ = I2cMsg(self.addr)
         self.msgBus_.open()
      return self.msgBus_

   def writeMsg(self, msg):
      self.msgBus.write_bytes(self.msgBus.addr.address, msg)
