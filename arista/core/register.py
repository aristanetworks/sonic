
import copy

from .log import getLogger

logging = getLogger(__name__)

class HardwareHandle(object):

   def __str__(self):
      raise NotImplementedError

   def read(self):
      raise NotImplementedError

   def write(self, value):
      raise NotImplementedError

   def shortName(self):
      raise NotImplementedError

   def fullName(self):
      raise NotImplementedError

   def log(self, fmt, *args):
      logging.io('%s ' + fmt, self.fullName(), *args)

class RegBitField(HardwareHandle):
   def __init__(self, bitpos, name, ro=True, flip=False, parent=None):
      '''Parent of this class is Register'''
      self.parent = parent
      self.bitpos = bitpos
      self.name = name
      self.ro = ro
      self.flip = flip

   def __str__(self):
      return '%s %s' % (self.parent.shortName(), self.shortName())

   def shortName(self):
      return 'Bit(%d, %s, ro=%s)' % (self.bitpos, self.name, self.ro)

   def fullName(self):
      return '%s %s' % (self.parent.fullName(), self.shortName())

   def read(self):
      value = self.parent.readBit(self.bitpos)
      if self.flip:
         value = not value
      self.log('read(): %#x', value)
      return value

   def write(self, value):
      assert not self.ro
      self.log('write(%#x)', value)
      if self.flip:
         value = not value
      return self.parent.writeBit(self.bitpos, value)

   def readWrite(self, value=None):
      if value is None:
         return self.read()
      return self.write(value)

   def getAttribute(self, parent=None):
      self.parent = parent
      return self.readWrite

class RegBitRange(HardwareHandle):
   def __init__(self, bitstart, bitend, name, ro=True, flip=False, parent=None):
      '''Parent of this class is Register'''
      self.parent = parent
      # bit start and end in range are inclusive
      self.bitstart = bitstart
      self.bitend = bitend
      self.name = name
      self.ro = ro
      self.flip = flip

   def __str__(self):
      return '%s %s' % (self.parent.shortName(), self.shortName())

   def shortName(self):
      return 'BitRange(%d, %d, %s, ro=%s)' % (self.bitstart, self.bitend,
                                              self.name, self.ro)

   def fullName(self):
      return '%s %s' % (self.parent.fullName(), self.shortName())

   def read(self):
      value = self.parent.readBits(self.bitstart, self.bitend)
      self.log('read(): %#x', value)
      if self.flip:
         mask = (1 << (self.bitend - self.bitstart + 1)) - 1
         value = ~value & mask
      return value

   def write(self, value):
      assert not self.ro
      self.log('write(%#x)', value)
      if self.flip:
         mask = (1 << (self.bitend - self.bitstart + 1)) - 1
         value = ~value & mask
      return self.parent.writeBits(self.bitstart, self.bitend, value)

   def readWrite(self, value=None):
      if value is None:
         return self.read()
      return self.write(value)

   def getAttribute(self, parent=None):
      self.parent = parent
      return self.readWrite

class Register(HardwareHandle):
   def __init__(self, addr, *fields, **kwargs):
      self.parent = kwargs.get('parent')
      self.addr = addr
      self.fields = fields
      self.name = kwargs.get('name')
      self.ro = kwargs.get('ro')
      self.default = kwargs.get('default')

   def __str__(self):
      return self.shortName()

   def shortName(self):
      return 'Register(%s, %s)' % (self.addr, self.name)

   def fullName(self):
      return '%s %s' % (self.parent, self)

   def split(self):
      pass

   def read(self):
      value = self.parent.read(self.addr)
      if self.name:
          self.log('read(): %#x', value)
      return value

   def write(self, value):
      if self.name:
          self.log('write(%#x)', value)
      return self.parent.write(self.addr, value)

   def readWrite(self, value=None):
      if value is None:
         return self.read()
      return self.write(value)

   def readBit(self, bitpos):
      return (self.read() >> bitpos) & 1

   def writeBit(self, bitpos, value):
      regval = self.read()
      if value:
         regval |= (1 << bitpos)
      else:
         regval &= ~(1 << bitpos)
      return self.write(regval)

   def readBits(self, bitstart, bitend):
      mask = (1 << (bitend - bitstart + 1)) - 1
      return (self.read() >> bitstart) & mask

   def writeBits(self, bitstart, bitend, value):
      mask = (1 << (bitend - bitstart + 1)) - 1
      regval = (self.read() & ~(mask << bitstart)) | (value << bitstart)
      return self.write(regval)

   def generateFieldAttributes(self, attrs, field):
      attrs[field.name] = field.getAttribute(self)

   def generateAttributes(self, parent=None):
      if parent is not None:
         self.parent = parent
      assert self.parent is not None

      attrs = {}
      if self.name:
         attrs[self.name] = self.readWrite
      for field in self.fields:
         if hasattr(field, 'getAttribute'):
            self.generateFieldAttributes(attrs, field)
      return attrs

class ClearOnReadRegister(Register):
   def __init__(self, addr, *fields, **kwargs):
      super(ClearOnReadRegister, self).__init__(addr, *fields, **kwargs)
      self.cache = 0

   def readBit(self, bitpos):
      bit = super(ClearOnReadRegister, self).readBit(bitpos)
      self.cache &= ~(1 << bitpos)
      return bit

   def read(self):
      self.cache |= super(ClearOnReadRegister, self).read()
      # NOTE: clear on read behavior for users only happens via a readBit
      return self.cache

class SetClearRegister(Register):
   def __init__(self, addrSet, addrClear, *fields, **kwargs):
      super(SetClearRegister, self).__init__(addrSet, *fields, **kwargs)
      self.addrSet = addrSet
      self.addrClear = addrClear

   def writeBit(self, bitpos, value):
      addr = self.addrSet if value else self.addrClear
      self.parent.write(addr, 1 << bitpos)

class RegisterMap(object):
   def __init__(self, parent, offset=0):
      self.parent_ = parent
      self.attributes_ = []
      self.offset = offset
      for key in dir(self):
         attr = getattr(self, key)
         if isinstance(attr, Register):
            self._updateAttributes(copy.deepcopy(attr))

   def _updateAttributes(self, reg):
      reg.addr += self.offset
      attrs = reg.generateAttributes(self.parent_)
      for key, value in attrs.items():
         self.attributes_.append(key)
         setattr(self, key, value)

   def __diag__(self, ctx):
      res = []
      for attr in self.attributes_:
         func = getattr(self, attr)
         try:
            value = func() if ctx.performIo else None
         except (IOError, NotImplementedError):
            value = False
         info = {
            'name': str(attr),
            'addr': str(func.__self__),
            'value': value
         }

         res.append(info)
      return res
