from dataclasses import dataclass
import os
import struct
from typing import Optional

DEFAULT_DMI_PATH = '/sys/firmware/dmi/entries'

@dataclass(frozen=True)
class DmiEntry:
   typ: int
   fields: dict[int, str]

   # For entries without a formatted section containing string indices,
   # decode the sole string as this field. Multiple strings are unsupported.
   defaultField: Optional[str] = None

   def path(self, basePath: str = DEFAULT_DMI_PATH, index: int = 0) -> str:
      return os.path.join(basePath, f'{self.typ}-{index}', 'raw')

   def paths(self, basePath: str = DEFAULT_DMI_PATH) -> list[str]:
      prefix = f'{self.typ}-'
      try:
         entries = os.listdir(basePath)
      except OSError:
         return []
      paths = []
      for entry in entries:
         if not entry.startswith(prefix):
            continue
         try:
            index = int(entry[len(prefix):])
         except ValueError:
            continue
         paths.append((index, os.path.join(basePath, entry, 'raw')))
      return [path for _, path in sorted(paths)]

   def exists(self, basePath: str = DEFAULT_DMI_PATH) -> bool:
      return os.path.exists(self.path(basePath))

   def decode(self, basePath: str = DEFAULT_DMI_PATH):
      return dmiReadAndDecode(self, basePath)

class DmiType:
   BIOS = DmiEntry(0, {
      0x04: 'Vendor',
      0x05: 'Version',
   })

   SYSTEM = DmiEntry(1, {
      0x04: 'Manufacturer',
      0x05: 'Product Name',
      0x06: 'Version',
   })

   BASEBOARD = DmiEntry(2, {
      0x04: 'Manufacturer',
      0x05: 'Product Name',
      0x06: 'Version',
   })

   MEMORY_DEVICE = DmiEntry(17, {
      0x10: 'Device Locator',
      0x11: 'Bank Locator',
      0x17: 'Manufacturer',
      0x18: 'Serial Number',
      0x19: 'Asset Tag',
      0x1a: 'Part Number',
   })

   # The vendor-specific PREFDL entry has no formatted fields; its sole
   # string is the Base64-encoded PREFDL payload.
   PREFDL = DmiEntry(128, {}, defaultField='Prefdl')

def dmiRead(entry: DmiEntry, basePath: str = DEFAULT_DMI_PATH) -> bytes:
   with open(entry.path(basePath), 'rb') as f:
      return f.read()

def dmiReadAll(entry: DmiEntry, basePath: str = DEFAULT_DMI_PATH) -> list[bytes]:
   data = []
   for path in entry.paths(basePath):
      try:
         with open(path, 'rb') as f:
            data.append(f.read())
      except OSError:
         continue
   return data

def dmiDecode(entry: DmiEntry, data: bytes) -> dict[str, str]:
   if len(data) < 4:
      return {}
   _, length, _ = struct.unpack_from('<BBH', data)
   strings = data[length:].rstrip(b'\x00').split(b'\x00')

   if entry.defaultField:
      if len(strings) != 1 or not strings[0]:
         return {}
      return {entry.defaultField: strings[0].decode('utf8')}

   decoded = {}
   for offset, name in entry.fields.items():
      if offset >= length:
         continue
      stringIndex = data[offset]
      if stringIndex == 0 or stringIndex > len(strings):
         continue
      decoded[name] = strings[stringIndex - 1].decode('utf8')
   return decoded

def dmiReadAndDecode(entry: DmiEntry,
                     basePath: str = DEFAULT_DMI_PATH) -> dict[str, str]:
   return dmiDecode(entry, dmiRead(entry, basePath))

def dmiReadAndDecodeAll(entry: DmiEntry,
                        basePath: str = DEFAULT_DMI_PATH) -> list[dict[str, str]]:
   return [dmiDecode(entry, data) for data in dmiReadAll(entry, basePath)]
