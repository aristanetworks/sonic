from __future__ import print_function, with_statement

import os

from collections import OrderedDict, namedtuple

# TODO: use core.component.pci.PciComponent
from ..core.component import Priority, PciComponent
from ..core.component.i2c import I2cComponent
from ..core.config import Config
from ..core.driver.kernel import KernelDriver
from ..core.fan import FanSlot
from ..core.types import I2cAddr, MdioClause, MdioSpeed
from ..core.utils import (
   FileWaiter,
   incrange,
   inSimulation,
   MmapResource,
   simulateWith,
   writeConfig
)
from ..core.log import getLogger
from ..core.register import (
   Register,
   RegisterMap,
   RegBitField,
   RegBitRange,
)
from ..core.xcvr import (
   OsfpSlot,
   QsfpSlot,
   SfpSlot,
   EthernetSlot,
)

from ..descs.fan import FanDesc, FanPosition
from ..descs.led import LedColor, LedDesc
from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.xcvr import Osfp, Qsfp, QsfpDD, Rj45, Sfp

from ..drivers.scd.driver import ScdI2cDevDriver, ScdKernelDriver
from ..drivers.scd.watchdog import ScdWatchdog
from ..drivers.scd.programmable import ScdProgrammable
from ..drivers.scd.cause import ( # pylint: disable=unused-import
   ScdCause,
   ScdReloadCauseProvider,
   SimpleScdReloadCauseProvider,
)
from ..drivers.scd.seu import ScdSeuReporter

from ..inventory.interrupt import Interrupt
from ..inventory.powercycle import PowerCycle

logging = getLogger(__name__)

SYS_UIO_PATH = '/sys/class/uio'

class ScdI2cAddr(I2cAddr):
   def __init__(self, scd, bus, addr, **kwargs):
      super().__init__(bus, addr, **kwargs)
      self.scd_ = scd

   @property
   def busName(self):
      return self.scd_.driver.getMasterNameForBus(self.bus_)

   @property
   def bus(self):
      return self.scd_.i2cOffset + self.bus_

class ScdPowerCycle(PowerCycle):
   def __init__(self, scd, reg=0x7000, wr=0xDEAD):
      self.scd = scd
      self.reg = reg
      self.wr = wr

   def ensureAvailable(self):
      pass

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

class ScdInterruptRegister():
   def __init__(self, scd, addr, num, mask):
      self.scd = scd
      self.num = num
      self.readAddr = addr
      self.setAddr = addr
      self.clearAddr = addr + 0x10
      self.statusAddr = addr + 0x20
      self.watchdogMask = 0
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
      writeConfig(self.scd.addr.getSysfsPath(), OrderedDict([
         ('interrupt_mask_read_offset%s' % self.num, str(self.readAddr)),
         ('interrupt_mask_set_offset%s' % self.num, str(self.setAddr)),
         ('interrupt_mask_clear_offset%s' % self.num, str(self.clearAddr)),
         ('interrupt_mask_watchdog%s' % self.num, str(self.watchdogMask)),
         ('interrupt_status_offset%s' % self.num, str(self.statusAddr)),
         ('interrupt_mask%s' % self.num, str(self.mask)),
      ]))

   def getInterruptBit(self, name, bit):
      if not Config().init_irq:
         return None
      if name == 'watchdog':
         self.watchdogMask = 1 << bit
      return self.scd.inventory.addInterrupt(ScdInterrupt(self, name, bit))

class ScdMdio():
   def __init__(self, scd, master, bus, devIdx, port, device, clause, name):
      self.scd = scd
      self.master = master
      self.bus = bus
      self.id = devIdx
      self.portAddr = port
      self.deviceAddr = device
      self.clause = clause
      self.name = name

class ScdSmbus():
   def __init__(self, scd, bus):
      self.scd = scd
      self.bus = bus

   def i2cAddr(self, addr):
      return self.scd.i2cAddr(self.bus, addr)


class Scd(PciComponent):
   BusTweak = namedtuple('BusTweak', 'addr, t, datr, datw, ed')
   def __init__(self, addr, registerCls=None, **kwargs):
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
      super().__init__(addr=addr, drivers=drivers, **kwargs)
      self.regs = self.drivers['scd-hwmon'].regs
      self.inventory.addProgrammable(ScdProgrammable(self))

   def __str__(self):
      return f'{self.__class__.__name__}(addr={self.addr})'

   def setMsiRearmOffset(self, offset):
      self.msiRearmOffset = offset

   def createPowerCycle(self, reg=0x7000, wr=0xDEAD):
      powerCycle = ScdPowerCycle(self, reg=reg, wr=wr)
      self.powerCycles.append(powerCycle)
      self.inventory.addPowerCycle(powerCycle)
      return powerCycle

   def getPowerCycles(self):
      return self.powerCycles

   def createWatchdog(self, reg=0x0120, intr=None, bit=None):
      watchdog = ScdWatchdog(self, reg=reg)
      self.inventory.addWatchdog(watchdog)
      if intr is not None and bit is not None:
         # Watchdog is handled via an interrupt and bit needs to be declared
         intr.getInterruptBit('watchdog', bit)
      return watchdog

   def createInterrupt(self, addr, num, mask=0xffffffff):
      interrupt = ScdInterruptRegister(self, addr, num, mask)
      self.interrupts.append(interrupt)
      return interrupt

   def getMmap(self):
      path = os.path.join(self.addr.getSysfsPath(), "resource0")
      if not self.mmapReady:
         # check that the scd driver is loaded the first time
         drv = self.drivers['scd']
         if not drv.loaded():
            # This codepath is unlikely to be used
            drv.setup()
            FileWaiter(path, 5).waitFileReady()
         self.mmapReady = True
      return MmapResource(path)

   def getVersion(self):
      if inSimulation():
         return hex(0x420001)
      with self.getMmap() as mm:
         return hex(mm.read32(0x100))

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

   def addFanGroup(self, addr, platform, slots, count):
      self.fanGroups += [(addr, platform, slots, count)]

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

   def _addXcvrSlot(self, cls, name, port, bus=None, addr=None, ledAddr=None,
                    ledAddrOffsetFn=lambda x: 0x10, intrRegs=None,
                    intrRegIdxFn=None, intrBitFn=None, **kwargs):
      intr = None
      if intrRegs:
         intrReg = intrRegs[intrRegIdxFn(port.index)]
         intr = intrReg.getInterruptBit(name, intrBitFn(port.index))
      presentGpio = None
      addrFunc = None
      if addr is not None and bus is not None:
         addrFunc = lambda addr, b=bus: self.i2cAddr(b, addr,
                                                     t=1, datr=0, datw=3, ed=0)
         presentDesc = GpioDesc("%s_present" % name, addr=addr, bit=2, ro=True,
                                activeLow=True)
         presentGpio = self.addXcvrGpio(presentDesc)
      leds = []
      for laneId in incrange(1, port.leds):
         laneName = name
         if port.leds > 1:
            laneName = "%s_%d" % (laneName, laneId)
         leds.append((ledAddr, laneName))
         ledAddr += ledAddrOffsetFn(port.index)
      ledGroup = self.addLedGroup(name, leds)
      return self.newComponent(
         cls=cls,
         name=name,
         slotId=port.index,
         addrFunc=addrFunc,
         interrupt=intr,
         presentGpio=presentGpio,
         leds=ledGroup,
         **kwargs
      )

   def _addEthernetSlot(self, port, prefix='rj45_', **kwargs):
      name = '%s%d' % (prefix, port.index)
      self._addXcvrSlot(cls=EthernetSlot, name=name, port=port, **kwargs)

   def _addSfpSlot(self, port, addr=None, **kwargs):
      name = 'sfp%d' % port.index
      rxLosDesc = GpioDesc("%s_rxlos" % name, addr, bit=0, ro=True)
      txDisableDesc = GpioDesc("%s_txdisable" % name, addr, bit=6)
      txFaultDesc = GpioDesc("%s_txfault" % name, addr, bit=1, ro=True)

      self.sfps += [(addr, port.index)]

      return self._addXcvrSlot(
         cls=SfpSlot,
         name=name,
         port=port,
         addr=addr,
         rxLosGpio=self.addXcvrGpio(rxLosDesc),
         txDisableGpio=self.addXcvrGpio(txDisableDesc),
         txFaultGpio=self.addXcvrGpio(txFaultDesc),
         **kwargs
      )

   def _addQsfpSlot(self, port, addr=None, isHwLpModeAvail=True,
                    isHwModSelAvail=True, **kwargs):
      name = 'qsfp%d' % port.index
      lpModeDesc = GpioDesc("%s_lp_mode" % name, addr=addr, bit=6)
      modSelDesc = GpioDesc("%s_modsel" % name, addr=addr, bit=8,
                            activeLow=True)
      resetDesc = ResetDesc("%s_reset" % name, addr=addr, bit=7)

      self.qsfps += [(addr, port.index)]

      return self._addXcvrSlot(
         cls=QsfpSlot,
         name=name,
         port=port,
         addr=addr,
         lpMode=self.addXcvrGpio(lpModeDesc) if isHwLpModeAvail else None,
         modSel=self.addXcvrGpio(modSelDesc) if isHwModSelAvail else None,
         reset=self.addXcvrReset(resetDesc),
         **kwargs
      )

   def _addOsfpSlot(self, port, addr=None, isHwLpModeAvail=True,
                    isHwModSelAvail=True, **kwargs):
      name = 'osfp%d' % port.index
      lpModeDesc = GpioDesc("%s_lp_mode" % name, addr=addr, bit=6)
      modSelDesc = GpioDesc("%s_modsel" % name, addr=addr, bit=8,
                            activeLow=True)
      resetDesc = ResetDesc("%s_reset" % name, addr=addr, bit=7)

      self.osfps += [(addr, port.index)]

      return self._addXcvrSlot(
         cls=OsfpSlot,
         name=name,
         port=port,
         addr=addr,
         lpMode=self.addXcvrGpio(lpModeDesc) if isHwLpModeAvail else None,
         modSel=self.addXcvrGpio(modSelDesc) if isHwModSelAvail else None,
         reset=self.addXcvrReset(resetDesc),
         **kwargs
      )

   def addXcvrSlots(self, ports, addr=None, bus=None, ledAddr=None,
                    addrOffset=0x10, busOffset=1, ledAddrOffsetFn=lambda x: 0x10,
                    **kwargs):
      for p in ports:
         func = None
         if isinstance(p, Rj45):
            func = self._addEthernetSlot
         elif isinstance(p, Sfp):
            func = self._addSfpSlot
         elif isinstance(p, QsfpDD):
            func = self._addOsfpSlot
         elif isinstance(p, Qsfp):
            func = self._addQsfpSlot
         elif isinstance(p, Osfp):
            func = self._addOsfpSlot
         else:
            raise ValueError( 'Unsupported xcvr %s by SCD' % p )
         func(port=p, addr=addr, bus=bus, ledAddr=ledAddr,
              ledAddrOffsetFn=ledAddrOffsetFn, **kwargs)
         if addr is not None:
            addr += addrOffset
         if ledAddr is not None:
            ledAddr += p.leds * ledAddrOffsetFn(p.index)
         if bus is not None:
            bus += busOffset

   def addFan(self, desc):
      return self.inventory.addFan(self.driver.getFan(desc))

   def addFanLed(self, desc):
      return self.inventory.addLed(self.driver.getFanLed(desc))

   def addFanSlotBlock(self, slotCount, fanCount, statusLed=None):
      for i, slotId in enumerate(incrange(1, slotCount)):
         self.addFanSlot(i, slotId, fanCount, statusLed=statusLed)

   def addFanSlot(self, idx, slotId, fanCount, statusLed=None):
      led = LedDesc(name='fan%d' % slotId,
                    colors=[LedColor.GREEN, LedColor.RED, LedColor.OFF])
      fanDescs = [FanDesc(fanId=idx * fanCount + j, position=list(FanPosition)[j])
                  for j in incrange(1, fanCount)]

      return self.newComponent(
         FanSlot,
         slotId=slotId,
         led=self.addLed(*statusLed) if statusLed else self.addFanLed(led),
         fans=[self.addFan(desc) for desc in fanDescs]
      )

   def addMdioMaster(self, addr, masterId, busCount=1, speed=MdioSpeed.S2_5):
      self.mdioMasters[addr] = {
         'id': masterId,
         'bus': busCount,
         'speed': speed,
         'devCount': [0] * busCount,
      }

   def addMdioMasterRange(self, base, count, spacing=0x40, busCount=1,
                          speed=MdioSpeed.S2_5):
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

   def addReloadCauseProvider(self, causes=None, regmap=None, addr=None,
                              priority=ScdCause.Priority.PRIMARY):
      if isinstance(addr, int):
         # Initial DPM-less reboot cause support e.g PikeZ
         rcp = SimpleScdReloadCauseProvider(self, addr, causes)
      else:
         rcp = ScdReloadCauseProvider(self, regmap, causes, priority=priority)
      return self.inventory.addReloadCauseProvider(rcp)

   def addSeuReporter(self, regmap):
      return self.inventory.addSeuReporter(ScdSeuReporter(self, regmap))

   def getResets(self, xcvrs=True, autoOnly=False):
      resets = [r for r in self.resets if not autoOnly or r.desc.auto == True]
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

class ScdReloadCauseRegisters(RegisterMap):
   LATCHED_CAUSE = Register(0x4F80,
      RegBitRange(0, 7, name='latchedCause'),
   )
   LATCHED_CAUSE_RTC0 = Register(0x4F84,
      RegBitRange(0, 15, name='latchedFractional'),
   )
   LATCHED_CAUSE_RTC1 = Register(0x4F88, name='latchedSeconds')
   LAST_CAUSE = Register(0x4F8C,
      RegBitRange(0, 7, name='lastCause'),
   )
   LAST_CAUSE_RTC0 = Register(0x4F90,
      RegBitRange(0, 15, name='lastFractional'),
   )
   LAST_CAUSE_RTC1 = Register(0x4F94, name='lastSeconds')
   RTC0 = Register(0x4FA8,
      RegBitRange(0, 15, name='rtcFractional', ro=False),
   )
   RTC1 = Register(0x4FAC, name='rtcSeconds', ro=False)
   CAUSE_CTRL = Register(0x4F98,
      RegBitField(0, name='clearFault', ro=False),
      RegBitRange(16, 31, name='faultTest', ro=False),
   )
