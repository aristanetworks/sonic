from contextlib import closing

from ..core.i2c_utils import I2cMsg
from ..core.log import getLogger

from .i2c import I2cDevDriver

logging = getLogger(__name__)

# cmd[0].rw: read/write command designation
PEX_I2C_RD = 0x4
PEX_I2C_WR = 0x3

# cmd[1].mode: transparent port, nt port, or dma engine
PEX_I2C_MODE_BRIGE = 0x0
PEX_I2C_MODE_NT_LINK = 0x1
PEX_I2C_MODE_NT_VIRT = 0x2
PEX_I2C_MODE_DMA = 0x3

# ffs(x) - 1, i.e. least significant bit set in x
def first_bit(x):
   return (x & -x).bit_length() - 1

class PlxPexI2cCommand(object):

   def __init__(self, c0, c1, c2, c3):
      self.cmd = [c0, c1, c2, c3]

   @classmethod
   def assemble(cls, rdwr, mode, port, bsel, addr):
      assert rdwr in [PEX_I2C_RD,
                      PEX_I2C_WR]
      assert mode in [PEX_I2C_MODE_BRIGE,
                      PEX_I2C_MODE_NT_LINK,
                      PEX_I2C_MODE_NT_VIRT,
                      PEX_I2C_MODE_DMA]
      assert 0 <= port < 32
      assert (bsel >> first_bit(bsel)) in [0x1, 0x3, 0xf]
      assert 0 <= addr < (256 << 10)
      assert addr & 0x3 == 0

      return cls(rdwr & 0xff,

                 ((mode & 0x3) << 4) |
                 ((port & 0x1e) >> 1),

                 ((port & 0x1) << 7) |
                 ((bsel & 0xf) << 2) |
                 ((addr >> 10) & 0x3), # addr[11:9]

                 ((addr >> 2) & 0xff)) # addr[9:2]

   # PEX i2c reads + writes are 32-bit aligned. The .bsel (byte
   # select) field is a 4-bit mask designating the significant data
   # bytes out of 4, to accomodate 8-bit and 16-bit register accesses.

   @staticmethod
   def align(addr, order):
      assert 0 <= order <= 2, \
         "Order %d is not in [0, 1, 2]" % order
      size = 1 << order
      assert (addr & (size - 1)) == 0, \
         "Misaligned %d-bit access @ %#x" % (size * 8, addr)
      bsel = ((1 << size) - 1) << (addr & 0x3)
      addr = addr & ~0x3
      return bsel, addr

   # 8/16/32-bit write val => 4-byte bsel-masked data
   def wrdata(self, val):
      r32 = val << (first_bit(self.bsel) * 8)
      return [
         ((val >> (24 - (i * 8))) & 0xff) \
         if (self.bsel & (1 << i)) else 0
         for i in range(0, 4)
      ]

   # 4-byte bsel-masked data => 8/16/32-bit read val
   def rdval(self, data):
      r32 = sum([
         data[3 - i] << (i * 8)
         for i in range(0, 4)
         if (self.bsel & (1 << i))
      ])
      return r32 >> (first_bit(self.bsel) * 8)

   @property
   def rdwr(self):
      return self.cmd[0]

   @property
   def mode(self):
      return (self.cmd[1] >> 4) & 0x3

   @property
   def port(self):
      return ((self.cmd[1] << 1) & 0x1e) | ((self.cmd[2] >> 7) & 0x1)

   @property
   def bsel(self):
      return (self.cmd[2] >> 2) & 0xf

   @property
   def addr(self):
      return ((self.cmd[2] & 0x3) << 10) | (self.cmd[3] << 2)

   def __len__(self):
      return len(self.cmd)

   def __iter__(self):
      return iter(self.cmd)

   def __str__(self):
      rdwr = { PEX_I2C_WR : 'wr',
               PEX_I2C_RD : 'rd' }[self.rdwr]
      mode = { PEX_I2C_MODE_BRIGE : 'br',
               PEX_I2C_MODE_NT_LINK : 'nt-l',
               PEX_I2C_MODE_NT_VIRT : 'nt-v',
               PEX_I2C_MODE_DMA : 'dma' }[self.mode]
      s = first_bit(self.bsel)
      r = { 0x1 : "r8",
            0x3 : "r16",
            0xf : "r32" }.get(self.bsel >> s)
      bsel = \
         "%s<<%d" % (r, s) if (r and s) \
         else r if r else hex(self.bsel)
      return \
         "%s(rdwr=%s, mode=%s, port=%d, bsel=%s, addr=%#x)" % (
            self.__class__.__name__,
            rdwr, mode, self.port, bsel, self.addr)

   def __repr__(self):
      return str(self)

class PlxPexI2cAddrMap(object):

   def mode(self, addr):
      raise NotImplementedError

   def port(self, addr):
      raise NotImplementedError

   def offset(self, addr):
      raise NotImplementedError

   def command(self, rdwr, order, addr):
      bsel, addr = PlxPexI2cCommand.align(addr, order)
      return PlxPexI2cCommand.assemble(rdwr,
                                       self.mode(addr),
                                       self.port(addr),
                                       bsel,
                                       self.offset(addr))

class PlxPexI2cPciAddrMap(PlxPexI2cAddrMap):
   # Address PEX registers over I2c, by emulating the same 256kb
   # address map as PCI BAR0. See "4.3.2 PCI Express Memory-Mapped
   # Configuration Space".

   class BrPort(PlxPexI2cAddrMap):
      MAX = 32
      POS = 0
      END = MAX << 12

      @classmethod
      def mode(cls, addr):
         return PEX_I2C_MODE_BRIGE

      @classmethod
      def port(cls, addr):
         return addr >> 12

      @classmethod
      def offset(cls, addr):
         return addr & 0xfff

   class NtPort(PlxPexI2cAddrMap):
      MAX = 2
      POS = 0x3c000
      END = POS + ((MAX * 2) << 12)

      @classmethod
      def idx(cls, addr):
         return (addr - cls.POS) >> 12

      @classmethod
      def mode(cls, addr):
         if cls.idx(addr) & 1:
            return PEX_I2C_MODE_NT_LINK
         else:
            return PEX_I2C_MODE_NT_VIRT

      @classmethod
      def port(cls, addr):
         return 1 - (cls.idx(addr) >> 1)

      @classmethod
      def offset(cls, addr):
         return addr & 0xfff

   @classmethod
   def portmap(cls, addr):
      for t in [cls.BrPort, cls.NtPort]:
         if t.POS <= addr and addr < t.END:
            return t
      raise NotImplementedError(
         "%s.portmap(%#x)" % (cls.__name__, addr))

   @classmethod
   def mode(cls, addr):
      return cls.portmap(addr).mode(addr)

   @classmethod
   def port(cls, addr):
      return cls.portmap(addr).port(addr)

   @classmethod
   def offset(cls, addr):
      return cls.portmap(addr).offset(addr)

class PlxPexI2cBrPortAddrMap(PlxPexI2cAddrMap):
   # relative to a given transparent port id

   def __init__(self, portId):
      self.portId = portId

   def mode(self, addr):
      return PEX_I2C_MODE_BRIGE

   def port(self, addr):
      return self.portId

   def offset(self, addr):
      return addr & 0xfff

class PlxPexI2cDevDriver(I2cDevDriver):

   PLX_ADDR_MAP = None

   def __init__(self, **kwargs):
      super(PlxPexI2cDevDriver, self).__init__(**kwargs)
      self.addrmap = self.PLX_ADDR_MAP()

   def _read(self, order, addr):
      cmd = self.addrmap.command(PEX_I2C_RD, order, addr)
      logging.debug("%s._read(%d, %#x): %s", self, order, addr, cmd)
      data = self.read_bytes(cmd, 4)
      logging.debug("%s.read_bytes([%s], 4) = [%s]", self,
                    ', '.join(["%#x" % c for c in cmd]),
                    ', '.join(["%#x" % d for d in data]))
      return cmd.rdval(data)

   def _write(self, order, addr, val):
      cmd = self.addrmap.command(PEX_I2C_WR, order, addr)
      logging.debug("%s._write(%d, %#x, %#x): %s", self, order, addr, val, cmd)
      data = cmd.wrdata(val)
      logging.debug("%s.write_bytes([%s] + [%s])", self,
                    ', '.join(["%#x" % c for c in cmd]),
                    ', '.join(["%#x" % d for d in data]))
      self.write_bytes(list(cmd) + data)

   def read(self, addr):
      return self._read(2, addr)

   def write(self, addr, val):
      return self._write(2, addr, val)

   def read16(self, addr):
      return self._read(1, addr)

   def write16(self, addr, val):
      return self._write(1, addr, val)

   def read8(self, addr):
      return self._read(0, addr)

   def write8(self, addr, val):
      return self._write(0, addr, val)

class PlxPex8700I2cDevDriver(PlxPexI2cDevDriver):

   PLX_ADDR_MAP = PlxPexI2cPciAddrMap

   def smbusPing(self):
      try:
         with self:
            v = self.read16(0x0)
            assert v == 0x10b5, \
               "%s: vendor id %#x is not PLX" % (self, v)
      except IOError as e:
         return False
      return True

   def enableHotPlug(self):
      # TODO. It does not work this way. SltCap bits can only be set
      # on transparent downstream ports. If anything, 0x7c would be
      # only (upstream) port 0.
      # (Until then, it does not hurt, writes to 0+0x7c won't latch)
      self.regs.hotPlugSurprise(True)
      self.regs.hotPlugCapable(True)

   def disableUpstreamPort(self, port, off):
      portDisableReg = self.regs.portDisable()
      if off:
          self.regs.portDisable(portDisableReg | (1 << port))
      else:
          self.regs.portDisable(portDisableReg & ~(1 << port))

   def setUpstreamPort(self, port):
      self.regs.upstreamPort(port)

   def setNtPort(self, port):
      self.regs.ntPort(port)

   def enableNt(self, on):
      self.regs.ntEnable(on)

   def vsPortVec(self, vsId, value=None):
      return [
         self.regs.vs0PortVec,
         self.regs.vs1PortVec,
      ][vsId](value)
