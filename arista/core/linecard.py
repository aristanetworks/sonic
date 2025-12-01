
from .component import Priority
from .card import Card
from .log import getLogger
from .provision import ProvisionMode
from .utils import inSimulation

from ..utils.rpc.client import RpcServerException
from ..utils.rpc.helper import RpcClientSource, getGlobalRpcClient

logging = getLogger(__name__)

class LCpuCtx(object):
   def __init__(self, provision=ProvisionMode.NONE):
      self.provision = provision

class Linecard(Card): # pylint: disable=abstract-method
   ABSOLUTE_CARD_OFFSET = 3

   def setup(self, filters=Priority.defaultFilter):
      super().setup(filters)
      if not inSimulation():
         try:
            rpc = getGlobalRpcClient(source=RpcClientSource.FROM_LINECARD)
            rpc.provisionComplete()
         except RpcServerException:
            logging.exception(
               '%s: provisionComplete RPC call to supervisor failed', self)
