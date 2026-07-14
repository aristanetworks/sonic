import asyncio
import os
from tempfile import TemporaryDirectory

from ....tests.testing import mock, unittest

from ..api import RpcSupervisorApi
from ..context import ClientContext
from ....components.denali.card import DenaliLinecardBase, DenaliLinecardSlot
from ....components.denali.linecard import DenaliLinecard
from ....core.card import CardSlot
from ....core.component import Priority
from ....core.linecard import Linecard
from ....core.platform import getPlatformSkus
from ....core.tests.mockchassis import MockSupervisor

from .... import platforms as _

class FakeProcess():
   async def communicate(self):
      self.returncode = 0
      return b'This is stdout', b'This is stderr'

class FakeReloadCauseManager():
   def __init__(self, ignore):
      pass

   def loadCauses(self):
      pass

   def toDict(self, latestOnly=False): # pylint: disable=unused-argument
      return {
         'name': 'foo',
         'version': 3,
         'reports': [
            {
               'date': '2022-10-11 13:00:00',
               'cause': 'unknown cause',
               'providers': [
                  {
                     'name': 'foo',
                     'causes': [
                        {
                           'cause': 'unknown cause',
                           'time': 'unknown',
                           'description': 'bar',
                        },
                     ],
                  },
               ],
            }
         ],
      }

class ClientTest(unittest.IsolatedAsyncioTestCase):
   def _newApi(self, platform=None, senderSlotId=None):
      api = RpcSupervisorApi(platform)
      ipaddr = ('127.0.0.1' if senderSlotId is None else
                f'127.100.{senderSlotId}.1')
      ctx = ClientContext((ipaddr, '43000'))
      return api, ctx

   def _doCreateLinecard(self, sup, cls):
      if issubclass(cls, DenaliLinecard):
         pci = sup.getPciPort(0x01)
         bus = sup.getSmbus(0x03)
         slotId = DenaliLinecard.ABSOLUTE_CARD_OFFSET
         slot = DenaliLinecardSlot(sup, slotId, pci, bus)
         sup.linecardSlots.append(slot)
      else:
         slot = CardSlot(None, 0)
      return cls(slot=slot)

   def _createMockChassis(self):
      sup = MockSupervisor()
      for _, linecardCls in getPlatformSkus().items():
         if not issubclass(linecardCls, Linecard):
            continue
         linecard = self._doCreateLinecard(sup, linecardCls)
         assert linecard
         for f in [None, Priority.defaultFilter, Priority.lateFilter]:
            linecard.setup(filters=f)
         return sup
      assert False, 'No linecard definitions available'

   async def testLinecardSetup(self):
      api, ctx = self._newApi()
      with mock.patch('asyncio.create_subprocess_exec') as mockObj:
         mockObj.side_effect = lambda *args, **kwargs: FakeProcess()
         result = await api.linecardSetup(ctx, 7)
         mockObj.assert_called_once_with('arista', '-l', '/var/log/arista-linecard.log',
                                         'linecard', '-i', '7', 'setup', '--lcpu', '--on',
                                         stdout=asyncio.subprocess.PIPE,
                                         stderr=asyncio.subprocess.PIPE)
         self.assertEqual(result, {
            'status': True,
            'detail': 'This is stdout\nThis is stderr'
         })

   async def testLinecardClean(self):
      api, ctx = self._newApi()
      with mock.patch('asyncio.create_subprocess_exec') as mockObj:
         mockObj.side_effect = lambda *args, **kwargs: FakeProcess()
         result = await api.linecardClean(ctx, 7)
         mockObj.assert_called_once_with('arista', '-l', '/var/log/arista-linecard.log',
                                         'linecard', '-i', '7', 'clean', '--lcpu', '--off',
                                         stdout=asyncio.subprocess.PIPE,
                                         stderr=asyncio.subprocess.PIPE)
         self.assertEqual(result, {
            'status': True,
            'detail': 'This is stdout\nThis is stderr'
         })

   async def testFabricSetup(self):
      api, ctx = self._newApi()
      with mock.patch('asyncio.create_subprocess_exec') as mockObj:
         mockObj.side_effect = lambda *args, **kwargs: FakeProcess()
         result = await api.fabricSetup(ctx, 54)
         mockObj.assert_called_once_with('arista', '-l', '/var/log/arista-fabric.log',
                                         'fabric', '-i', '54', 'setup', '--on',
                                         stdout=asyncio.subprocess.PIPE,
                                         stderr=asyncio.subprocess.PIPE)
         self.assertEqual(result, {
            'status': True,
            'detail': 'This is stdout\nThis is stderr'
         })

   async def testFabricClean(self):
      api, ctx = self._newApi()
      with mock.patch('asyncio.create_subprocess_exec') as mockObj:
         mockObj.side_effect = lambda *args, **kwargs: FakeProcess()
         result = await api.fabricClean(ctx, 54)
         mockObj.assert_called_once_with('arista', '-l', '/var/log/arista-fabric.log',
                                         'fabric', '-i', '54', 'clean',
                                         stdout=asyncio.subprocess.PIPE,
                                         stderr=asyncio.subprocess.PIPE)
         self.assertEqual(result, {
            'status': True,
            'detail': 'This is stdout\nThis is stderr'
         })

   async def testReloadCause(self):
      sup = self._createMockChassis()
      api, ctx = self._newApi(platform=sup,
                              senderSlotId=DenaliLinecardBase.ABSOLUTE_CARD_OFFSET)
      with mock.patch('arista.utils.rpc.api.getLinecardReloadCauseManager') as mockRCM, \
           mock.patch('arista.components.cookie.flashPath') as flashPathMock, \
           TemporaryDirectory(prefix='cookies') as tempdir:
         mockRCM.side_effect = lambda *args, **kwargs: FakeReloadCauseManager(None)
         flashPathMock.side_effect = lambda *args: os.path.join(tempdir, *args)
         os.makedirs(os.path.join(tempdir, 'reboot-cause', 'platform'))
         result = await api.getLinecardRebootCause(ctx)
         mockRCM.assert_called_once()
         self.assertIn('reports', result)
         self.assertIn('providers', result['reports'][0])
         self.assertIn('causes', result['reports'][0]['providers'][0])

if __name__ == '__main__':
   unittest.main()
