from __future__ import print_function

from contextlib import closing
from io import BytesIO
import re
import zlib

from .log import getLogger

logging = getLogger(__name__)

class InvalidPrefdlData( Exception ):
   pass

class TlvField(object):
   def __init__(self, code, name, length=None, aliases=None, value=None):
      self.name = name
      self.code = code
      self.length = length
      self.value = value
      self.aliases = aliases or []

   def __str__(self):
      return '%s(%#02x, %s)' % (self.__class__.__name__, self.code, self.name)

   def __call__(self, value):
      return self.__class__(self.code, self.name, self.length, self.aliases, value)

   def toStr(self):
      return self.value

   def parse(self, value):
      raise NotImplementedError

   def check(self, value):
      return True

class TlvStrField(TlvField):
   def parse(self, value):
      if isinstance(value, str):
         return value
      return value.decode('ascii')

class TlvIntField(TlvField):
   def parse(self, value):
      return int(value)

   def toStr(self):
      return str(self.value)

class TlvMacField(TlvStrField):
   def parse(self, value):
      v = super(TlvMacField, self).parse(value)
      if ':' in v:
         return v
      return ":".join([v[0:2], v[2:4], v[4:6], v[6:8], v[8:10], v[10:12]])

class TlvIntTupleField(TlvStrField):
   def parse(self, value):
      value = super(TlvIntTupleField, self).parse(value)
      return tuple(int(v) for v in value.split('.'))

   def toStr(self):
      return '.'.join('%02d' % v for v in self.value)

class TlvSerialField(TlvStrField):
   def check(self, value):
      v = value.replace(" ", "").replace("-", "").upper()
      if re.match(r"[A-Z]{3}\d{4}[A-Z0-9]{4}$", v):
         return True
      return False

class PrefdlBase(object):
   FIELDS = [
      TlvField(0x00, 'END', length=0),
      TlvStrField(0x01, 'Deviation'),
      TlvStrField(0x02, 'MfgTime'),
      TlvStrField(0x03, 'SKU', aliases=['Sku']),
      TlvStrField(0x04, 'ASY'),
      TlvMacField(0x05, 'MAC', aliases=['MacAddrBase', 'Mac']),
      TlvIntTupleField(0x0a, 'HwApi'),
      TlvIntTupleField(0x0b, 'HwRev'),
      TlvStrField(0x0c, 'SID', aliases=['Sid']),
      TlvStrField(0x0d, 'PCA', length=12),
      TlvSerialField(0x0e, 'SerialNumber', length=11),
      TlvStrField(0x0f, 'KVN', length=3),
      TlvStrField(0x17, 'MfgTime2'),
   ]

   FIELD_CODE = {f.code : f for f in FIELDS}
   FIELD_NAME = {f.name : f for f in FIELDS}
   FIELD_NAME.update({a : f for f in FIELDS for a in f.aliases})

   def __init__(self, f=None, data=None, version=b''):
      self._data = {}
      self._fields = []
      self._buffer = version
      self._crc = 0xffffffff
      self._crcOk = True
      if data:
         self.parseData(data)
      if f:
         self.parseFile(f)

   def data(self):
      return self._data

   def toDict(self):
      return {field.name: field.toStr() for field in self._fields}

   def toList(self):
      return [(field.code, field.name, field.toStr()) for field in self._fields]

   def getField(self, name):
      return self._data.get(name)

   def getCrc(self):
      return self._crc

   def getRaw(self):
      return self._buffer

   def isCrcValid(self):
      return self._crcOk

   def show(self):
      for key, value in sorted(self.toDict().items()):
         print("%s: %s" % (key, value))

   def preParse(self, f):
      pass

   def checkCrc(self, f):
      expected = int(f.read(8), 16)
      computed = zlib.crc32(self._buffer) & 0xffffffff
      if expected != computed:
         logging.error('Eeprom CRC mismatch %#08x vs %#08x', expected, computed)
         self._crcOk = False
      self._crc = computed

   def parseData(self, data):
      for k, v in data.items():
         field = self.FIELD_NAME.get(k)
         if field is None:
            continue
         self.addField(field, v)

   def parseFile(self, f):
      self.preParse(f)
      while self.parseTlvField(f):
         pass
      self.checkCrc(f)

   def addField(self, field, value):
      v = self._data.get(field.name)
      if v is not None:
         logging.warning('Eeprom field %s already set with %s', field.name, v)
      value = field.parse(value)
      if not field.check(value):
         logging.warning('Field value %s does not meet %s expectation', value, field)
         return
      self._fields.append(field(value))
      self._data[field.name] = value

   def readTlv(self, f):
      code = f.read(2)
      length = f.read(4)
      self._buffer += code + length
      code = int(code, 16)
      length = int(length, 16)
      value = f.read(length)
      self._buffer += value
      return code, value

   def parseFixedField(self, field, f):
      value = f.read(field.length)
      self._buffer += value
      self.addField(field, value)

   def parseTlvField(self, f):
      code, value = self.readTlv(f)
      if code == 0x00:
         return False

      field = self.FIELD_CODE.get(code)
      if field:
         self.addField(field, value)
      return True

   def writeToFile(self, path):
      with open(path, 'w') as f:
         for k, v in self.toDict().items():
            f.write('%s: %s\n' % (k, v))

class PrefdlV2(PrefdlBase):
   def preParse(self, f):
      self.parseFixedField(self.FIELD_NAME['PCA'], f)
      self.parseFixedField(self.FIELD_NAME['SerialNumber'], f)
      self.parseFixedField(self.FIELD_NAME['KVN'], f)

class PrefdlV3(PrefdlBase):
   pass

class UnknownPrefdlVersion(Exception):
   pass

class Prefdl(object):
   MAP = {
      b"0002": PrefdlV2,
      b"0003": PrefdlV3,
   }

   @classmethod
   def getPrefdlCls(cls, version):
      try:
         return cls.MAP[version]
      except KeyError:
         raise UnknownPrefdlVersion("unknown prefdl verison %s" % version)

   @classmethod
   def fromBinFile(cls, path, version=None, skip=0):
      with open(path, mode='rb') as f:
         if skip:
            f.read(skip)
         version = version or f.read(4)
         return cls.getPrefdlCls(version)(f=f, version=version)

   @classmethod
   def fromBytes(cls, data, version=None):
      with closing(BytesIO(data)) as f:
         version = version or f.read(4) # pylint: disable=no-member
         return cls.getPrefdlCls(version)(f=f, version=version)

   @classmethod
   def fromDict(cls, data):
      return PrefdlBase(data=data)

   @classmethod
   def fromTextFile(cls, path):
      data = {}
      with open(path, mode='r') as f:
         for line in f.readlines():
            line = line.rstrip()
            if not line:
               continue
            try:
               key, value = line.split(': ', 1)
            except ValueError:
               logging.warning('Failed to parse field "%s"', line)
               continue
            data[key] = value
      return cls.fromDict(data)
