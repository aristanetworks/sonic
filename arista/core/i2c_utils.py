from ctypes import \
   c_uint8, \
   c_uint16, \
   c_uint32, \
   POINTER, \
   Structure, \
   sizeof, \
   cast, \
   pointer
from fcntl import ioctl
from .log import getLogger

logging = getLogger(__name__)

I2C_M_RD = 0x0001
I2C_M_RECV_LEN = 0x0400

I2C_RDWR = 0x0707

I2C_SMBUS_BLOCK_MAX = 32

class i2c_msg(Structure):
   _fields_ = [
      ('addr', c_uint16),
      ('flags', c_uint16),
      ('len', c_uint16),
      ('buf', POINTER(c_uint8))
   ]

   def __str__(self):
      return "%s(%#x, %#x, %d, [%s])" % (
         self.__class__.__name__,
         self.addr, self.flags, self.len,
         ', '.join([
            "%#x" % self.buf[i]
            for i in range(self.len)
         ]))

   def __repr__(self):
      return str(self)

class i2c_rdwr_ioctl_data(Structure):
   _fields_ = [
      ('msgs', POINTER(i2c_msg)),
      ('nmsgs', c_uint32)
   ]

   @classmethod
   def write_bytes(cls, addr, wrbuf):
      msg_data = (i2c_msg * 1)(
         i2c_msg(addr, 0,
                 sizeof(wrbuf.contents),
                 cast(wrbuf, POINTER(c_uint8)))
      )
      return cls(msg_data, 1)

   @classmethod
   def read_bytes(cls, addr, wrbuf, rdbuf):
      msg_data = (i2c_msg * 2)(
         i2c_msg(addr, 0,
                 sizeof(wrbuf.contents),
                 cast(wrbuf, POINTER(c_uint8))),
         i2c_msg(addr, I2C_M_RD,
                 sizeof(rdbuf.contents),
                 cast(rdbuf, POINTER(c_uint8)))
      )
      return cls(msg_data, 2)

   @classmethod
   def read_block(cls, addr, wrbuf, rdbuf):
      msg_data = (i2c_msg * 2)(
         i2c_msg(addr, 0,
                 sizeof(wrbuf.contents),
                 cast(wrbuf, POINTER(c_uint8))),
         i2c_msg(addr, I2C_M_RD | I2C_M_RECV_LEN,
                 sizeof(rdbuf.contents),
                 cast(rdbuf, POINTER(c_uint8)))
      )
      return cls(msg_data, 2)

   def __str__(self):
      return "%s(%s)" % (
         self.__class__.__name__,
         [self.msgs[i] for i in range(self.nmsgs)])

   def __repr__(self):
      return str(self)

class I2cMsg(object):
   def __init__(self, addr):
      self.addr = addr
      self.device = None

   def __str__(self):
      return '%s(%s, fd=%d)' % (
         self.__class__.__name__,
         self.addr,
         self.device.fileno() if self.device else -1)

   def open(self):
      if self.device is None:
         self.device = open("/dev/i2c-%d" % self.addr.bus, 'r+b', buffering=0)

   def close(self):
      if self.device:
         self.device.close()
         self.device = None

   def __enter__(self):
      self.open()
      return self

   def __exit__(self, *args):
      self.close()

   def i2c_rdwr(self, data):
      logging.io('%s.i2c_rdwr(%s) ..', self, data) # user msgs
      try:
         ret = ioctl(self.device.fileno(), I2C_RDWR, data)
      except IOError as e:
         ret = -e.errno
         raise
      except:
         ret = None
         raise
      finally:
         logging.io('%s.i2c_rdwr(%s): ret=%s',
                       self, data, ret) # kernel msgs

   def write_bytes(self, addr, cmd):
      wrbuf = (c_uint8 * len(cmd))(*cmd)
      ioctl_data = i2c_rdwr_ioctl_data.write_bytes(addr,
                                                   pointer(wrbuf))
      self.i2c_rdwr(ioctl_data)

   def read_bytes(self, addr, cmd, datalen):
      wrbuf = (c_uint8 * len(cmd))(*cmd)
      rdbuf = (c_uint8 * datalen)()
      ioctl_data = i2c_rdwr_ioctl_data.read_bytes(addr,
                                                  pointer(wrbuf),
                                                  pointer(rdbuf))
      self.i2c_rdwr(ioctl_data)
      return [c for c in rdbuf]

   def read_block(self, addr, cmd):
      wrbuf = (c_uint8 * len(cmd))(*cmd)
      rdbuf = (c_uint8 * (1 + I2C_SMBUS_BLOCK_MAX))( 1 )
      ioctl_data = i2c_rdwr_ioctl_data.read_block(addr,
                                                  pointer(wrbuf),
                                                  pointer(rdbuf))
      self.i2c_rdwr(ioctl_data)
      return [rdbuf[i] for i in range(ioctl_data.msgs[1].len)]
