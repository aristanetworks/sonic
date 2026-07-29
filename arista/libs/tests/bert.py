import struct
import tempfile
import uuid
from unittest.mock import patch

from ...tests.testing import unittest
from ..bert import getBertDetail

PROC_GENERIC_UUID = uuid.UUID('9876ccad-47b4-4bdb-b65e-16f193c4f3db')
MEMORY_UUID = uuid.UUID('a5bc1114-6f64-4ede-b863-3e83ed7c83b1')

def _make_bert_data(entries):
   """Build a raw BERT binary blob from a list of entry dicts.

   Each entry: section_uuid, severity, revision, fru_text='', extra_data=b''
   Returns bytes with a valid status block header prepended.
   """
   dataEntries = b''
   for e in entries:
      sectionUuid = e['uuid']
      severity = e.get('severity', 1)
      revision = e.get('revision', 0x200)
      fruText = e.get('fru_text', '').encode('ascii').ljust(20, b'\x00')[:20]
      extraData = e.get('extra_data', b'')
      dataHeader = (
         sectionUuid.bytes_le +
         struct.pack('<IHBBI', severity, revision, 0, 0, len(extraData)) +
         b'\x00' * 16 +   # fru_id
         fruText
      )
      if revision >= 0x300:
         dataHeader += b'\x00' * 8  # timestamp
      dataEntries += dataHeader + extraData
   statusHeader = struct.pack('<IIIII', 0, 0, 0, len(dataEntries), 0)
   return statusHeader + dataEntries

class GetBertDetailTest(unittest.TestCase):
   def _write_and_call(self, data):
      with tempfile.NamedTemporaryFile() as f:
         f.write(data)
         f.flush()
         with patch('arista.libs.bert.BERT_DATA_PATH', f.name):
            return getBertDetail()

   def testFileNotFound(self):
      with patch('arista.libs.bert.BERT_DATA_PATH', '/nonexistent/bert'):
         self.assertIsNone(getBertDetail())

   def testReturnsNoneOnBadData(self):
      cases = [
         ('file too short', b'\x00' * 4),
         ('zero data length', struct.pack('<IIIII', 0, 0, 0, 0, 0)),
      ]
      for name, data in cases:
         with self.subTest(name):
            self.assertIsNone(self._write_and_call(data))

   def testParseEntries(self):
      cases = [
         (
            'single entry',
            [{'uuid': PROC_GENERIC_UUID, 'severity': 1}],
            ['Processor Generic error, severity: Fatal'],
         ),
         (
            'multiple entries',
            [
               {'uuid': PROC_GENERIC_UUID, 'severity': 1},
               {'uuid': MEMORY_UUID, 'severity': 2, 'fru_text': 'DIMM_A1'},
            ],
            [
               'Processor Generic error, severity: Fatal',
               'Memory error, severity: Corrected, FRU: DIMM_A1',
            ],
         ),
         (
            'extra data skipped',
            [
               {'uuid': PROC_GENERIC_UUID, 'severity': 1,
                'extra_data': b'\xff' * 32},
               {'uuid': MEMORY_UUID, 'severity': 3},
            ],
            [
               'Processor Generic error, severity: Fatal',
               'Memory error, severity: Informational',
            ],
         ),
      ]
      for name, entries, expected in cases:
         with self.subTest(name):
            result = self._write_and_call(_make_bert_data(entries))
            self.assertEqual(result, expected)
