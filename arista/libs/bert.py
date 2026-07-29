import os
import struct
import uuid

from ..core.log import getLogger

logging = getLogger(__name__)

BERT_DATA_PATH = '/sys/firmware/acpi/tables/data/BERT'

_SECTION_TYPES = {
   uuid.UUID('9876ccad-47b4-4bdb-b65e-16f193c4f3db'): 'Processor Generic',
   uuid.UUID('dc3ea0b0-a144-4797-b95b-53fa242b6e1d'): 'IA32/X64 Processor',
   uuid.UUID('e19e3d16-bc11-11e4-9caa-c2051d5d46b0'): 'ARM Processor',
   uuid.UUID('a5bc1114-6f64-4ede-b863-3e83ed7c83b1'): 'Memory',
   uuid.UUID('d995e954-bbc1-430f-ad91-b44dcb3c6f35'): 'PCIe',
}

_SEVERITY_NAMES = {
   0: 'Recoverable',
   1: 'Fatal',
   2: 'Corrected',
   3: 'Informational',
}

# Generic Error Status Block header (20 bytes):
#   block_status      4
#   raw_data_offset   4
#   raw_data_length   4
#   data_length       4
#   error_severity    4
_STATUS_HEADER_SIZE = 20

# Generic Error Data Entry (64 bytes base, 72 bytes when revision >= 0x0300):
#   section_type     16   offset  0
#   error_severity    4   offset 16
#   revision          2   offset 20
#   validation_bits   1   offset 22
#   flags             1   offset 23
#   error_data_length 4   offset 24
#   fru_id           16   offset 28
#   fru_text         20   offset 44
#   timestamp         8   offset 64 (revision >= 0x0300)
_DATA_HEADER_SIZE = 64
_DATA_HEADER_SIZE_V3 = 72

def _parseEntries(data, dataLen):
   entries = []
   offset = _STATUS_HEADER_SIZE
   end = _STATUS_HEADER_SIZE + dataLen
   while offset < end:
      if offset + _DATA_HEADER_SIZE > len(data):
         logging.warning('BERT data truncated at offset %d: need %d bytes, '
                         '%d available', offset, _DATA_HEADER_SIZE,
                         len(data) - offset)
         break
      sectionType = _SECTION_TYPES.get(
         uuid.UUID(bytes_le=bytes(data[offset:offset + 16])), 'Unknown')
      severity, revision, _, _, errorDataLen = struct.unpack_from(
         '<IHBBI', data, offset + 16)
      fruText = (data[offset + 44:offset + 64]
                 .rstrip(b'\x00').decode('ascii', errors='replace').strip())
      headerSize = _DATA_HEADER_SIZE_V3 if revision >= 0x300 else _DATA_HEADER_SIZE
      desc = (f'{sectionType} error, '
              f'severity: {_SEVERITY_NAMES.get(severity, severity)}')
      if fruText:
         desc += f', FRU: {fruText}'
      entries.append(desc)
      offset += headerSize + errorDataLen
   return entries

def getBertDetail():
   if not os.path.exists(BERT_DATA_PATH):
      return None
   try:
      with open(BERT_DATA_PATH, 'rb') as f:
         data = f.read()
      if len(data) < _STATUS_HEADER_SIZE:
         return None
      dataLen = struct.unpack_from('<I', data, 12)[0]
      if not dataLen:
         return None
      return _parseEntries(data, dataLen) or None
   except OSError as e:
      logging.debug('failed to read BERT data: %s', e)
      return None
