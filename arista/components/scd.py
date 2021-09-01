from __future__ import print_function, with_statement

import os

from collections import OrderedDict, namedtuple

# TODO: use core.component.pci.I2cComponent
from ..core.component import Priority, PciComponent
from ..core.component.i2c import I2cComponent
from ..core.config import Config
from ..core.driver import KernelDriver
from ..core.types import I2cAddr, MdioClause, MdioSpeed
from ..core.utils import (
   FileWaiter,
   incrange,
   MmapResource,
   simulateWith,
   writeConfig
)
from ..core.log import getLogger
from ..core.xcvr import (
   OsfpSlot,
   QsfpSlot,
   SfpSlot
)

from ..descs.led import LedDesc
from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc

from ..drivers.scd.driver import ScdI2cDevDriver, ScdKernelDriver

from ..inventory.interrupt import Interrupt
from ..inventory.powercycle import PowerCycle
from ..inventory.watchdog import Watchdog

from ..libs.python import monotonicRaw

logging = getLogger(__name__)

SYS_UIO_PATH = '/sys/class/uio'

class ScdI2cAddr(I2cAddr):
   def __init__(self, scd, bus, addr, **kwargs):
      super(ScdI2cAddr, self).__init__(bus, addr, **kwargs)
      self.scd_ = scd

   @property
   def busName(self):
      return self.scd_.driver.getMasterNameForBus(self.bus_)

   @property
   def bus(self):
      return self.scd_.i2cOffset + self.bus_

class ScdWatchdog(Watchdog):
   MAX_TIMEOUT = 65535

   def __init__(self, scd, reg=0x0120):
      self.scd = scd
      self.reg = reg
      self.armTimeStamp = 0

   @staticmethod
   def armReg(timeout):
      regValue = 0
      if timeout > 0:
         # Set enable bit
         regValue |= 1 << 31
         # Powercycle
         regValue |= 2 << 29
         # Timeout value
         regValue |= timeout
      return regValue

   def armSim(self, timeout):
      if timeout > ScdWatchdog.MAX_TIMEOUT:
         logging.error("watchdog timeout %s exceeds max timeout %s",
                       timeout, ScdWatchdog.MAX_TIMEOUT)
         return False
      self.armTimeStamp = monotonicRaw()
      regValue = self.armReg(timeout)
      logging.info("watchdog arm reg={0:32b}".format(regValue))
      return True

   @simulateWith(armSim)
   def arm(self, timeout):
      if timeout > ScdWatchdog.MAX_TIMEOUT:
         logging.error("watchdog timeout %s exceeds max timeout %s",
                       timeout, ScdWatchdog.MAX_TIMEOUT)
         return False
      self.armTimeStamp = monotonicRaw()
      regValue = self.armReg(timeout)
      try:
         with self.scd.getMmap() as mmap:
            logging.info('arm reg = {0:32b}'.format(regValue))
            mmap.write32(self.reg, regValue)
      except RuntimeError as e:
         logging.error("watchdog arm/stop error: {}".format(e))
         return False
      return True

   def stopSim(self):
      logging.info("watchdog stop")
      return True

   @simulateWith(stopSim)
   def stop(self):
      return self.arm(0)

   def statusSim(self):
      logging.info("watchdog status")
      return { "enabled": True, "timeout": 300, "remainingTime": 100 }

   @simulateWith(statusSim)
   def status(self):
      try:
         with self.scd.getMmap() as mmap:
            regValue = mmap.read32(self.reg)
            enabled = bool(regValue >> 31)
            timeout = regValue & ((1<<16)-1)
         # No HW support for retrieving remaining time, so it needs to be done
         # here instead. Will only be correct if ran from the same process that
         # armed the watchdog; otherwise the remaining time will be 0.
         if not enabled:
            remainingTime = -1
         else:
            remainingTime = 0
            if self.armTimeStamp > 0:
               timeDiff = 100 * int(monotonicRaw() - self.armTimeStamp)
               remainingTime = timeout - timeDiff
         return { "enabled": enabled, "timeout": timeout,
                  "remainingTime": remainingTime }
      except RuntimeError as e:
         logging.error("watchdog status error: {}".format(e))
         return None

class ScdPowerCycle(PowerCycle):
   def __init__(self, scd, reg=0x7000, wr=0xDEAD):
      self.scd = scd
      self.reg = reg
      self.wr = wr

   def powerCycle(self):
      logging.info("Initiating powercycle through SCD")
      try:
         with self.scd.getMmap() as mmap:
            mmap.write32(self.reg, self.wr)
            logging.info("Powercycle triggered by SCD")
            return True
      except RuntimeError as e:
         logging.error("powercycle error: %s", e)
         return False

class ScdInterrupt(Interrupt):
   def __init__(self, reg, name, bit):
      self.reg = reg
      self.name = name
      self.bit = bit

   def set(self):
      self.reg.setMask(self.bit)

   def clear(self):
      self.reg.clearMask(self.bit)

   def getName(self):
      return self.name

   def getFile(self):
      return self.reg.scd.getUio(self.reg.num, self.bit)

class ScdInterruptRegister(object):
   def __init__(self, scd, addr, num, mask):
      self.scd = scd
      self.num = num
      self.readAddr = addr
      self.setAddr = addr
      self.clearAddr = addr + 0x10
      self.statusAddr = addr + 0x20
      self.mask = mask

   def setReg(self, reg, wr):
      try:
         with self.scd.getMmap() as mmap:
            mmap.write32(reg, wr)
            return True
      except RuntimeError as e:
         logging.error("write register %s with %s: %s", reg, wr, e)
         return False

   def readReg(self, reg):
      try:
         with self.scd.getMmap() as mmap:
            res = mmap.read32(reg)
            return hex(res)
      except RuntimeError as e:
         logging.error("read register %s: %s", reg, e)
         return None

   def setMask(self, bit):
      mask = 0 | 1 << bit
      res = self.readReg(self.setAddr)
      if res is not None:
         self.setReg(self.setAddr, (mask | int(res, 16)) & 0xffffffff)

   def clearMask(self, bit):
      mask = 0 | 1 << bit
      res = self.readReg(self.setAddr)
      if res is not None:
         self.setReg(self.clearAddr, (mask | ~int(res, 16)) & 0xffffffff)

   def setup(self):
      if not Config().init_irq:
         return
      writeConfig(self.scd.pciSysfs, OrderedDict([
         ('interrupt_mask_read_offset%s' % self.num, str(self.readAddr)),
         ('interrupt_mask_set_offset%s' % self.num, str(self.setAddr)),
         ('interrupt_mask_clear_offset%s' % self.num, str(self.clearAddr)),
         ('interrupt_status_offset%s' % self.num, str(self.statusAddr)),
         ('interrupt_mask%s' % self.num, str(self.mask)),
      ]))

   def getInterruptBit(self, name, bit):
      if not Config().init_irq:
         return None
      return self.scd.inventory.addInterrupt(ScdInterrupt(self, name, bit))

class ScdMdio(object):
   def __init__(self, scd, master, bus, devIdx, port, device, clause, name):
      self.scd = scd
      self.master = master
      self.bus = bus
      self.id = devIdx
      self.portAddr = port
      self.deviceAddr = device
      self.clause = clause
      self.name = name

class ScdSmbus(object):
   def __init__(self, scd, bus):
      self.scd = scd
      self.bus = bus

   def i2cAddr(self, addr):
      return self.scd.i2cAddr(self.bus, addr)

class Scd(PciComponent):
   BusTweak = namedtuple('BusTweak', 'addr, t, datr, datw, ed')
   def __init__(self, addr, registerCls=None, **kwargs):
      self.pciSysfs = addr.getSysfsPath()
      drivers = [
         KernelDriver(module='scd'),
         ScdKernelDriver(scd=self, addr=addr, registerCls=registerCls),
      ]
      self.driver = drivers[1]
      self.smbusMasters = OrderedDict()
      self.mmapReady = False
      self.interrupts = []
      self.fanGroups = []
      self.leds = []
      self.gpios = []
      self.powerCycles = []
      self.osfps = []
      self.qsfps = []
      self.sfps = []
      self.tweaks = {}
      self.uioMap = {}
      self.resets = []
      self.i2cOffset = 0
      self.mdioMasters = {}
      self.mdios = []
      self.msiRearmOffset = None
      self.uartPorts = {}
      super(Scd, self).__init__(addr=addr, drivers=drivers, **kwargs)
      self.regs = self.drivers['scd-hwmon'].regs

   def __str__(self):
      return '%s()' % self.__class__.__name__

   def setMsiRearmOffset(self, offset):
      self.msiRearmOffset = offset

   def createPowerCycle(self, reg=0x7000, wr=0xDEAD):
      powerCycle = ScdPowerCycle(self, reg=reg, wr=wr)
      self.powerCycles.append(powerCycle)
      self.inventory.addPowerCycle(powerCycle)
      return powerCycle

   def getPowerCycles(self):
      return self.powerCycles

   def createWatchdog(self, reg=0x0120):
      watchdog = ScdWatchdog(self, reg=reg)
      self.inventory.addWatchdog(watchdog)
      return watchdog

   def createInterrupt(self, addr, num, mask=0xffffffff):
      interrupt = ScdInterruptRegister(self, addr, num, mask)
      self.interrupts.append(interrupt)
      return interrupt

   def getMmap(self):
      path = os.path.join(self.pciSysfs, "resource0")
      if not self.mmapReady:
         # check that the scd driver is loaded the first time
         drv = self.drivers['scd']
         if not drv.loaded():
            # This codepath is unlikely to be used
            drv.setup()
            FileWaiter(path, 5).waitFileReady()
         self.mmapReady = True
      return MmapResource(path)

   def i2cAddr(self, bus, addr, t=1, datr=3, datw=3, ed=0, block=True):
      i2cAddr = ScdI2cAddr(self, bus, addr, block=block)
      self.tweaks[(bus, addr)] = Scd.BusTweak(i2cAddr, t, datr, datw, ed)
      return i2cAddr

   def getSmbus(self, bus):
      return ScdSmbus(self, bus)

   def getInterrupts(self):
      return self.interrupts

   def getInterrupt(self, interruptId):
      return self.interrupts[interruptId]

   def addBusTweak(self, addr, t=1, datr=3, datw=3, ed=0):
      self.i2cAddr(addr.bus, addr.address, t=t, datr=datr, datw=datw, ed=ed )

   def addSmbusMaster(self, addr, mid, bus=8):
      self.smbusMasters[addr] = {
         'id': mid,
         'bus': bus,
      }

   def addSmbusMasterRange(self, addrStart, count, spacing=0x100, bus=8):
      addrs = range(addrStart, addrStart + (count + 1) * spacing, spacing)
      for i, addr in enumerate(addrs, 0):
         self.addSmbusMaster(addr, i, bus)

   def addFanGroup(self, addr, platform, num):
      self.fanGroups += [(addr, platform, num)]

   def _addLed(self, addr, name, **kwargs):
      desc = LedDesc(name=name)
      self.leds += [(addr, name)]
      return self.driver.getLed(desc, **kwargs)

   def addLed(self, addr, name, **kwargs):
      return self.inventory.addLed(self._addLed(addr, name, **kwargs))

   def addLeds(self, leds, **kwargs):
      return [self.addLed(*led, **kwargs) for led in leds]

   def addLedGroup(self, groupName, leds):
      leds = [self._addLed(*led) for led in leds]
      self.inventory.addLedGroup(groupName, leds)
      return leds

   def addReset(self, desc, **kwargs):
      reset = self.driver.getReset(desc, **kwargs)
      self.resets += [reset]
      return self.inventory.addReset(reset)

   def addResets(self, descs, **kwargs):
      return [self.addReset(desc, **kwargs) for desc in descs]

   def addGpio(self, desc, **kwargs):
      gpio = self.driver.getGpio(desc, **kwargs)
      self.gpios += [gpio]
      return self.inventory.addGpio(gpio)

   def addGpios(self, descs, **kwargs):
      return [self.addGpio(desc, **kwargs) for desc in descs]

   def addXcvrGpio(self, desc, **kwargs):
      # Note: separate adder to avoid conflicting with kernel driver
      return self.inventory.addGpio(self.driver.getGpio(desc, **kwargs))

   def addXcvrReset(self, desc, **kwargs):
      # Note: separate adder to avoid conflicting with kernel driver
      return self.inventory.addReset(self.driver.getReset(desc, **kwargs))

   def _addXcvrSlot(self, cls, name, xcvrId, addr, bus, ledAddr, ledAddrOffsetFn,
                    ledLanes, intrRegs=None, intrRegIdxFn=None,
                    intrBitFn=None, **kwargs):
      intr = None
      if intrRegs:
         intrReg = intrRegs[intrRegIdxFn(xcvrId)]
         intr = intrReg.getInterruptBit(name, intrBitFn(xcvrId))

      addrFunc = lambda addr, b=bus: self.i2cAddr(b, addr, t=1, datr=0, datw=3, ed=0)
      presentDesc = GpioDesc("%s_present" % name, addr=addr, bit=2, ro=True,
                             activeLow=True)

      leds = []
      for laneId in incrange(1, ledLanes):
         laneName = name
         if ledLanes > 1:
            laneName = "%s_%d" % (laneName, laneId)
         leds.append((ledAddr, laneName))
         ledAddr += ledAddrOffsetFn(xcvrId)
      ledGroup = self.addLedGroup(name, leds)

      return self.newComponent(
         cls=cls,
         name=name,
         slotId=xcvrId,
         addrFunc=addrFunc,
         interrupt=intr,
         presentGpio=self.addXcvrGpio(presentDesc),
         leds=ledGroup,
         **kwargs
      )

   def addSfpSlotBlock(self, sfpRange, addr, bus, ledAddr, addrOffset=0x10,
                       busOffset=1, ledAddrOffsetFn=lambda x: 0x10, ledLanes=1,
                       **kwargs):
      for i in sfpRange:
         self.addSfpSlot(xcvrId=i, addr=addr, bus=bus,
                         ledAddr=ledAddr, ledAddrOffsetFn=ledAddrOffsetFn,
                         ledLanes=ledLanes, **kwargs)
         addr += addrOffset
         bus += busOffset
         for _ in range(ledLanes):
            ledAddr += ledAddrOffsetFn(i)

   def addSfpSlot(self, xcvrId, addr, **kwargs):
      name = 'sfp%d' % xcvrId
      rxLosDesc = GpioDesc("%s_rxlos" % name, addr, bit=0, ro=True)
      txDisableDesc = GpioDesc("%s_txdisable" % name, addr, bit=6)
      txFaultDesc = GpioDesc("%s_txfault" % name, addr, bit=1, ro=True)

      self.sfps += [(addr, xcvrId)]

      return self._addXcvrSlot(
         cls=SfpSlot,
         name=name,
         xcvrId=xcvrId,
         addr=addr,
         rxLosGpio=self.addXcvrGpio(rxLosDesc),
         txDisableGpio=self.addXcvrGpio(txDisableDesc),
         txFaultGpio=self.addXcvrGpio(txFaultDesc),
         **kwargs
      )

   def addQsfpSlotBlock(self, qsfpRange, addr, bus, ledAddr, addrOffset=0x10,
                        busOffset=1, ledAddrOffsetFn=lambda x: 0x10, ledLanes=1,
                        **kwargs):
      for i in qsfpRange:
         self.addQsfpSlot(xcvrId=i, addr=addr, bus=bus,
                          ledAddr=ledAddr, ledAddrOffsetFn=ledAddrOffsetFn,
                          ledLanes=ledLanes, **kwargs)
         addr += addrOffset
         bus += busOffset
         for _ in range(ledLanes):
            ledAddr += ledAddrOffsetFn(i)

   def addQsfpSlot(self, xcvrId, addr, isHwLpModeAvail=True,
                   isHwModSelAvail=True, **kwargs):
      name = 'qsfp%d' % xcvrId
      lpModeDesc = GpioDesc("%s_lp_mode" % name, addr=addr, bit=6)
      modSelDesc = GpioDesc("%s_modsel" % name, addr=addr, bit=8, activeLow=True)
      resetDesc = ResetDesc("%s_reset" % name, addr=addr, bit=7)

      self.qsfps += [(addr, xcvrId)]

      return self._addXcvrSlot(
         cls=QsfpSlot,
         name=name,
         xcvrId=xcvrId,
         addr=addr,
         lpMode=self.addXcvrGpio(lpModeDesc) if isHwLpModeAvail else None,
         modSel=self.addXcvrGpio(modSelDesc) if isHwModSelAvail else None,
         reset=self.addXcvrReset(resetDesc),
         **kwargs
      )

   def addOsfpSlotBlock(self, osfpRange, addr, bus, ledAddr, addrOffset=0x10,
                        busOffset=1, ledAddrOffsetFn=lambda x: 0x10, ledLanes=1,
                        **kwargs):
      for i in osfpRange:
         self.addOsfpSlot(xcvrId=i, addr=addr, bus=bus,
                          ledAddr=ledAddr, ledAddrOffsetFn=ledAddrOffsetFn,
                          ledLanes=ledLanes, **kwargs)
         addr += addrOffset
         bus += busOffset
         for _ in range(ledLanes):
            ledAddr += ledAddrOffsetFn(i)

   def addOsfpSlot(self, xcvrId, addr, isHwLpModeAvail=True, isHwModSelAvail=True,
                   **kwargs):
      name = 'osfp%d' % xcvrId
      lpModeDesc = GpioDesc("%s_lp_mode" % name, addr=addr, bit=6)
      modSelDesc = GpioDesc("%s_modsel" % name, addr=addr, bit=8, activeLow=True)
      resetDesc = ResetDesc("%s_reset" % name, addr=addr, bit=7)

      self.osfps += [(addr, xcvrId)]

      return self._addXcvrSlot(
         cls=OsfpSlot,
         name=name,
         xcvrId=xcvrId,
         addr=addr,
         lpMode=self.addXcvrGpio(lpModeDesc) if isHwLpModeAvail else None,
         modSel=self.addXcvrGpio(modSelDesc) if isHwModSelAvail else None,
         reset=self.addXcvrReset(resetDesc),
         **kwargs
      )

   def addFan(self, desc):
      return self.inventory.addFan(self.driver.getFan(desc))

   def addFanLed(self, desc):
      return self.inventory.addLed(self.driver.getFanLed(desc))

   def addMdioMaster(self, addr, masterId, busCount=1, speed=MdioSpeed.S2_5):
      self.mdioMasters[addr] = {
         'id': masterId,
         'bus': busCount,
         'speed': speed,
         'devCount': [0] * busCount,
      }

   def addMdioMasterRange(self, base, count, spacing=0x40, busCount=1, speed=MdioSpeed.S2_5):
      addrs = range(base, base + count * spacing, spacing)
      for i, addr in enumerate(addrs, 0):
         self.addMdioMaster(addr, i, busCount, speed=speed)

   def addMdio(self, master, portAddr, bus=0, devAddr=1, clause=MdioClause.C45):
      addrs = [k for k, v in self.mdioMasters.items() if v['id'] == master]
      assert len(addrs) == 1, 'Mdio bus cannot be determined'
      assert bus < self.mdioMasters[addrs[0]]['bus'], 'Bus number is too large'

      devIndex = self.mdioMasters[addrs[0]]['devCount'][bus]
      self.mdioMasters[addrs[0]]['devCount'][bus] += 1
      name = "mdio{}_{}_{}".format(master, bus, devIndex)
      mdio = ScdMdio(self, master, bus, devIndex, portAddr, devAddr, clause, name)
      self.mdios.append(mdio)
      return mdio

   def addUartPort(self, addr, portId):
      self.uartPorts[addr] = {
         'id': portId,
      }

   def addUartPortRange(self, base, count, spacing=0x10):
      addrs = range(base, base + count * spacing, spacing)
      for i, addr in enumerate(addrs, 0):
         self.addUartPort(addr, i)

   def getResets(self, xcvrs=True):
      resets = self.resets
      if xcvrs:
         resets += [self.inventory.getReset('qsfp%d_reset' % xcvrId)
                    for _, xcvrId in self.qsfps]
         resets += [self.inventory.getReset('osfp%d_reset' % xcvrId)
                    for _, xcvrId in self.osfps]
      return resets

   def uioMapInit(self):
      for uio in os.listdir(SYS_UIO_PATH):
         with open(os.path.join(SYS_UIO_PATH, uio, 'name')) as uioName:
            self.uioMap[uioName.read().strip()] = uio

   def simGetUio(self, reg, bit):
      return '/dev/uio-%s-%x-%d' % (self.addr, reg, bit)

   @simulateWith(simGetUio)
   def getUio(self, reg, bit):
      if not self.uioMap:
         self.uioMapInit()
      return '/dev/%s' % self.uioMap[
            'uio-%s-%x-%d' % (getattr(self, 'addr'), reg, bit)]

class I2cScd(I2cComponent):
   # XXX: This class should probably be part of the Scd but since it's already a pci
   #      device, another class is necessary until we find a better model.

   DRIVER = ScdI2cDevDriver
   PRIORITY = Priority.DEFAULT

   def __getattr__(self, key):
      return getattr(self.driver.regs, key)
