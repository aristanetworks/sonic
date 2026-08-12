from errno import EAGAIN
import json
import os
import select
import socket
import threading

from ....tests.testing import mock, unittest

from ..client import RpcClient, RpcClientException, RpcServerException


class LoopbackServer():
   """Run a small scripted TCP server and report worker failures to the test."""

   TIMEOUT = 2

   def __init__(self, handler):
      self.handler = handler
      self.requests = []
      self.error = None
      self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      self.listener.bind(('127.0.0.1', 0))
      self.listener.listen()
      self.listener.settimeout(self.TIMEOUT)
      self.port = self.listener.getsockname()[1]
      self.worker = threading.Thread(target=self._run)

   def start(self):
      self.worker.start()

   def _run(self):
      try:
         self.handler(self)
      except Exception as error: # pylint: disable=broad-except
         self.error = error
      finally:
         self.listener.close()

   def accept(self):
      connection, _ = self.listener.accept()
      connection.settimeout(self.TIMEOUT)
      return connection

   def readRequest(self, connection):
      data = b''
      while not data.endswith(b'\n'):
         segment = connection.recv(RpcClient.READ_LENGTH)
         assert segment, 'client closed connection before sending a request'
         data += segment
      request = json.loads(data.decode('utf-8'))
      self.requests.append(request)
      return request

   def close(self):
      self.listener.close()
      self.worker.join(self.TIMEOUT)
      assert not self.worker.is_alive(), 'loopback RPC server did not finish'
      if self.error is not None:
         raise self.error

class FakeSocket():
   def __init__(self):
      self.sent_data = b''
      self.recv_data = b''
      self.response_data = b''

   def sendall(self, data):
      self.sent_data += data
      self.recv_data += self.response_data
      self.response_data = b''

   def recv(self, size):
      if not self.recv_data:
         raise OSError(EAGAIN, os.strerror(EAGAIN))
      chunk = self.recv_data[:size]
      self.recv_data = self.recv_data[size:]
      return chunk

   def settimeout(self, limit):
      pass

   def fileno(self):
      return 1023

class FakeEpoll():
   def __init__(self):
      self.polls = {}

   def register(self, fileno, flags):
      self.polls[fileno] = flags & ~(select.EPOLLERR|select.EPOLLHUP)

   def unregister(self, fileno):
      del self.polls[fileno]

   def poll(self, timeout):
      return list(self.polls.items())

class ClientTest(unittest.TestCase):
   HOST = 'localhost'
   PORT = '12345'

   def _newClient(self):
      client = RpcClient(ClientTest.HOST, ClientTest.PORT)
      client._connectSocket()
      return client

   def _newLoopbackClient(self, server):
      client = RpcClient('127.0.0.1', server.port)
      self.addCleanup(self._closeClient, client)
      return client

   @staticmethod
   def _closeClient(client):
      if client.sock is not None:
         client.sock.close()
      client.poller.close()

   def _startLoopbackServer(self, handler):
      server = LoopbackServer(handler)
      self.addCleanup(server.close)
      server.start()
      return server

   def testDoCommandData(self):
      with mock.patch('socket.create_connection') as createMock, \
           mock.patch('arista.utils.rpc.client.epoll') as epollMock:
         createMock.side_effect = lambda x: FakeSocket()
         epollMock.side_effect = FakeEpoll
         api = self._newClient()
         api.sock.response_data = b'{"jsonrpc": "2.0", "id": 0, "result": null}'
         api.doCommand('test')
         self.assertEqual(json.loads(api.sock.sent_data.decode('utf-8')),
                          {'jsonrpc': '2.0', 'method': 'test', 'params': None, 'id': 0})

   def testCommandError(self):
      with mock.patch('socket.create_connection') as createMock, \
           mock.patch('arista.utils.rpc.client.epoll') as epollMock:
         createMock.side_effect = lambda x: FakeSocket()
         epollMock.side_effect = FakeEpoll
         api = self._newClient()
         api.sock.response_data = b'{"jsonrpc": "2.0", "id": 0, "error": {"code": -1, "message": "foo"}}'
         with self.assertRaises(RpcServerException):
            api.doCommand('test')

   def testWrongVersion(self):
      with mock.patch('socket.create_connection') as createMock, \
           mock.patch('arista.utils.rpc.client.epoll') as epollMock:
         createMock.side_effect = lambda x: FakeSocket()
         epollMock.side_effect = FakeEpoll
         api = self._newClient()
         api.sock.response_data = b'{"jsonrpc": "3.0", "id": 0, "result": null}'
         with self.assertRaises(RpcClientException):
            api.doCommand('test')

   def testWrongId(self):
      with mock.patch('socket.create_connection') as createMock, \
           mock.patch('arista.utils.rpc.client.epoll') as epollMock:
         createMock.side_effect = lambda x: FakeSocket()
         epollMock.side_effect = FakeEpoll
         api = self._newClient()
         api.sock.response_data = b'{"jsonrpc": "2.0", "id": 1, "result": null}'
         with self.assertRaises(RpcClientException):
            api.doCommand('test')

   def testNoResult(self):
      with mock.patch('socket.create_connection') as createMock, \
           mock.patch('arista.utils.rpc.client.epoll') as epollMock:
         createMock.side_effect = lambda x: FakeSocket()
         epollMock.side_effect = FakeEpoll
         api = self._newClient()
         api.sock.response_data = b'{"jsonrpc": "2.0", "id": 0}'
         with self.assertRaises(RpcClientException):
            api.doCommand('test')

   def testRetriesAfterConnectionLoss(self):
      result = {'setup': 'complete'}

      def handle(server):
         with server.accept() as connection:
            server.readRequest(connection)

         with server.accept() as connection:
            request = server.readRequest(connection)
            connection.sendall(json.dumps({
               'jsonrpc': '2.0', 'id': request['id'], 'result': result,
            }).encode('utf-8') + b'\n')
            threading.Event().wait(0.1)

      server = self._startLoopbackServer(handle)
      client = self._newLoopbackClient(server)

      with mock.patch('arista.utils.rpc.client.time.sleep'):
         self.assertEqual(client.doCommand('linecardSetup', 7), result)

      self.assertEqual(len(server.requests), 2)
      self.assertEqual(server.requests[0], server.requests[1])

   def testReassemblesSegmentedResponse(self):
      result = 'x' * (RpcClient.READ_LENGTH * 2)

      def handle(server):
         with server.accept() as connection:
            request = server.readRequest(connection)
            response = json.dumps({
               'jsonrpc': '2.0', 'id': request['id'], 'result': result,
            }).encode('utf-8') + b'\n'
            for segment in (response[:100], response[100:4200], response[4200:]):
               connection.sendall(segment)
               threading.Event().wait(0.02)

      server = self._startLoopbackServer(handle)
      client = self._newLoopbackClient(server)

      self.assertEqual(client.doCommand('test'), result)

if __name__ == '__main__':
   unittest.main()
