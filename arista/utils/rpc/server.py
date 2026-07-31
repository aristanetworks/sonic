import asyncio
import json

from ...core.log import getLogger
from .constants import JsonRpcError, JSONRPC_VERSION
from .context import ClientContext

logging = getLogger(__name__)

class RpcServer():

   READER_MSG_SIZE = 4096

   def __init__(self, hosts, port, api):
      self.hosts = hosts
      self.port = port
      self.api = api

   def __str__(self):
      return self.__class__.__name__

   async def start(self):
      for host in self.hosts:
         logging.info('%s: listening on %s:%s', self, host, self.port)
         await asyncio.start_server(self.handleConnection, host, self.port,
                                    reuse_port=True)

   def response(self, result, uid=None, id_present=True):
      return json.dumps({
         'jsonrpc': JSONRPC_VERSION,
         'result': result,
         'id': uid,
      }) if id_present else None

   def errorResponse(self, code, message, uid=None, id_present=True):
      return json.dumps({
         'jsonrpc': JSONRPC_VERSION,
         'error': {
            'code': code,
            'message': message,
         },
         'id': uid,
      }) if id_present else None

   async def handleRequest(self, ctx, request):
      uid = request.get('id', None)
      id_present = 'id' in request

      if request.get('jsonrpc') != JSONRPC_VERSION:
         return self.errorResponse(
            JsonRpcError.INTERNAL_ERROR,
            'This server only implements the JSON-RPC 2.0 protocol',
            uid=uid, id_present=id_present)

      if 'method' not in request:
         return self.errorResponse(JsonRpcError.INVALID_REQUEST,
                                   'Missing field "method"',
                                   uid=uid, id_present=id_present)

      methodName = request['method']
      if methodName not in list(self.api.methods()):
         return self.errorResponse(JsonRpcError.METHOD_NOT_FOUND,
                                   f'No such method "{methodName}"',
                                   uid=uid, id_present=id_present)
      method = getattr(self.api, methodName)

      params = request.get('params', None)
      try:
         result = None
         if params is None:
            result = await method(ctx)
         elif isinstance(params, list):
            result = await method(ctx, *params)
         elif isinstance(params, dict):
            argList = []
            if '_args' in params:
               argList = params[ '_args' ]
               del params[ '_args' ]
            result = await method(ctx, *argList, **params)
         else:
            return self.errorResponse(JsonRpcError.INVALID_PARAMS,
                                      'params is not array or object',
                                      uid=uid, id_present=id_present)
         return self.response(result, uid=uid, id_present=id_present)
      except TypeError as e:
         logging.exception('%s: error while processing request for %s', self,
                           methodName)
         return self.errorResponse(JsonRpcError.INVALID_PARAMS,
                                   str(e),
                                   uid=uid, id_present=id_present)
      except Exception as e: #pylint: disable=broad-except
         logging.exception('%s: error while processing request for %s', self,
                           methodName)
         return self.errorResponse(-1,
                                   str(e),
                                   uid=uid, id_present=id_present)

   async def _handleMessage(self, ctx, message):
      logging.debug('%s: Received %r from %s', self, message, ctx.addr)
      if message is None:
         return self.errorResponse(JsonRpcError.PARSE_ERROR, 'Parse Error')

      if isinstance(message, dict):
         return await self.handleRequest(ctx, message)

      if isinstance(message, list):
         return await asyncio.gather(self.handleRequest(ctx, m) for m in message)

      return json.dumps({
         'jsonrpc': '2.0',
         'id': None,
         'error': {
            'code': JsonRpcError.INVALID_REQUEST,
            'message': 'JSON is not a valid JSON-RPC request',
         },
      })

   async def handleConnection(self, reader, writer):
      ctx = ClientContext(writer.get_extra_info('peername'))
      logging.info('%s: New connection from %s', self, ctx)
      exitReason = 'closed'
      try:
         data = b''
         while not reader.at_eof():
            try:
               data = await reader.read(self.READER_MSG_SIZE)
            except ConnectionResetError:
               exitReason = 'reset'
               return
            message = None
            try:
               message = json.loads(data)
               reader.feed_eof()
            except ValueError:
               pass

            response = await self._handleMessage(ctx, message)

            if response:
               response += '\n'
               logging.debug('%s: Send %r to %s', self, response, ctx)
               writer.write(response.encode('utf-8'))
            else:
               logging.debug('%s: No response for %s', self, ctx)

            self.api.tasks = [x for x in self.api.tasks if not x.done()]
            await asyncio.sleep(0)
      except: # pylint: disable=bare-except
         logging.exception('%s: Failed to handle request for %s', self, ctx)
         response = self.errorResponse(JsonRpcError.INTERNAL_ERROR,
                                       'Internal error',
                                       uid=None)
         if response:
            response += '\n'
            writer.write(response.encode('utf-8'))
      finally:
         logging.info('%s: Connection %s for %s', self, exitReason, ctx)
         writer.close()
         await writer.wait_closed()
