import errno
import json
from json.decoder import JSONDecodeError
from select import epoll, EPOLLERR, EPOLLHUP, EPOLLIN
import socket
import time

from ...core.log import getLogger

from .api import RpcSupervisorApi, RpcLinecardApi
from .constants import JSONRPC_VERSION

logging = getLogger(__name__)

class RpcClientException(Exception):
   def __init__(self, message):
      Exception.__init__(self, message)
      self.message = message

class RpcServerException(Exception):
   def __init__(self, error):
      Exception.__init__(self, error)
      self.code = error.get('code', None)
      self.message = error.get('message', None)

class RpcClient():
   """JSON-RPC client implementation.

   The methods that are supported are dynamically added to this class as they
   are run. A complete list of methods is provided by "RpcApi.methods".

   This client implementation is *not* thread-safe."""
   def __init__(self, host, port):
      self.poller = epoll()
      self.host = host
      self.port = port
      self.sock = None
      self._next_id = 0

   def next_id(self):
      uid = self._next_id
      self._next_id += 1
      return uid

   def _connectSocket(self):
      for delay in [1, 2, 4, 8]:
         try:
            self.sock = socket.create_connection((self.host, self.port))
            self.sock.settimeout(0)

            # Ideally we would use Edge Triggered here, but I don't think that can
            # actually work because of the timeout on receiving socket data, which
            # could trigger an event later that we wouldn't be able to block waiting
            # for.
            self.poller.register(self.sock.fileno(), EPOLLIN|EPOLLERR|EPOLLHUP)
         except OSError:
            time.sleep(delay)


   def _clearSocket(self):
      """Clear any leftover delayed responses on the socket"""
      while True:
         try:
            self.sock.recv(4096)
         except OSError as e:
            if e.errno == errno.EAGAIN:
               # No data to receive on the socket
               break
            raise

   def _sendCommand(self, command):
      return self.sock.sendall(command)

   def _readResponse(self, timeout=5):
      # Wait for data to become available on the socket
      events = self.poller.poll(timeout)
      if not events:
         raise TimeoutError()
      for _, event in events:
         if event == EPOLLIN:
            break
         raise ConnectionResetError()

      # Read all data from the socket; we need to keep trying to receive until we
      # get EAGAIN from the recv call, or we will potentially only get the first
      # part of the response if the response contains a lot of output.
      buf = b''
      try:
         while True:
            buf += self.sock.recv(4096)
      except OSError as e:
         if e.errno != errno.EAGAIN:
            raise

      return buf.decode('utf-8')

   def _processResponse(self, responseStr, uid):
      response = json.loads(responseStr)

      if response.get('jsonrpc') != JSONRPC_VERSION:
         raise RpcClientException(f'Got unexpected JsonRpc version {response.get("jsonrpc")}')
      if response.get('id') != uid:
         raise RpcClientException(f'Got unexpected message id {response.get("id")}, expected {uid}')
      if 'error' in response:
         raise RpcServerException(response['error'])
      if 'result' not in response:
         raise RpcClientException(f'Neither result nor error in JsonRpc response for message {uid}')
      return response['result']

   def _doGetCommandResponse(self, uid):
      attempts = 0
      responseStr = ""
      while attempts < 10:
         segment = self._readResponse()
         if segment is not None:
            responseStr += segment
            try:
               return self._processResponse(responseStr, uid)
            except JSONDecodeError:
               # This is likely because we got an incomplete message segment,
               # so just retry
               pass
         attempts += 1
      if not responseStr:
         raise RpcClientException('JSON-RPC server did not respond')
      raise RpcClientException(f'Could not decode JSON-RPC server response for message {uid}: {responseStr}')

   def doCommand(self, call, *args, **kwargs):
      if self.sock is None:
         self._connectSocket()
      uid = self.next_id()
      params = args
      if not params:
         params = kwargs
      if not params:
         params = None
      command = json.dumps({
         'jsonrpc': JSONRPC_VERSION,
         'method': call,
         'params': params,
         'id': uid}) + '\n'

      self._clearSocket()
      # Allow reconnecting the socket if the connection dies; if we timeout twice then give up.
      for _ in range(2):
         self._sendCommand(command.encode('utf-8'))
         try:
            return self._doGetCommandResponse(uid)
         except OSError:
            # Try disconnecting and reconnecting the socket then try again.
            self.poller.unregister(self.sock)
            self.sock.close()
            self._connectSocket()
      raise RpcClientException('JSON-RPC server did not respond')

   def __getattr__(self, name):
      if name not in RpcSupervisorApi.methods() and \
         name not in RpcLinecardApi.methods():
         return super().__getattr__(name)

      def fn(*args, **kwargs):
         return self.doCommand(name, *args, **kwargs)
      fn.__name__ = name
      setattr(self, name, fn)
      return fn
