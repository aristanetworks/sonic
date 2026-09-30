from ..adm1266 import Adm1266

from ....core.inventory import Inventory


def testBlackboxFaultsAreReturnedEarliestFirst():
   # Complete 65-byte READ_BLACKBOX responses: byte count, fault fields,
   # timestamp, reserved bytes, and CRC. Slot 0 has the empty bit set.
   responses = (
      bytes.fromhex(
         '40 00 10 01 00 10 00 00 00 00 00 00 00 00 00 00 00 00 00 '
         '00 00 00 00 07 00 00 00 80 85 74 67 00 00'
      ) + bytes(31) + b'\xa0',
      bytes.fromhex(
         '40 01 10 00 01 11 01 01 00 00 00 00 00 00 00 01 00 00 00 '
         '00 00 00 00 07 00 00 00 81 85 74 67 00 00'
      ) + bytes(31) + b'\xa1',
      bytes.fromhex(
         '40 02 10 00 02 22 00 02 00 01 00 02 00 00 00 02 00 01 00 '
         '04 00 00 00 07 00 00 00 82 85 74 67 00 00'
      ) + bytes(31) + b'\xa2',
      bytes.fromhex(
         '40 03 10 00 03 33 10 03 00 02 00 00 00 04 00 40 00 02 00 '
         '08 00 04 00 08 00 00 00 83 85 74 67 00 00'
      ) + bytes(31) + b'\xa3',
   )
   adm = Adm1266(inventory=Inventory())
   driver = adm.driver
   readIndices = []
   # Index 1 is newest, so slot 2 is earliest in the full circular buffer.
   driver.getBlackboxInfo = lambda: (0x1234, 1, len(responses))

   def readBytes(command, length):
      assert command[:2] == [driver.registers.READ_BLACKBOX, 1]
      assert length == 65
      index = command[2]
      readIndices.append(index)
      return responses[index]

   driver.read_bytes = readBytes
   faults = driver.getBlackboxFaults()

   assert readIndices == [2, 3, 0, 1]
   assert [fault.uid for fault in faults] == [0x1002, 0x1003, 0x1001]
   assert [fault.action for fault in faults] == [2, 3, 1]
