
from .component import Priority
from .card import Card
from .provision import ProvisionMode
from .utils import inSimulation

from ..utils.rpc.helper import RpcClientSource, getGlobalRpcClient

class LCpuCtx(object):
   def __init__(self, provision=ProvisionMode.NONE):
      self.provision = provision

class Linecard(Card): # pylint: disable=abstract-method
   ABSOLUTE_CARD_OFFSET = 3

   def setup(self, filters=Priority.defaultFilter):
      super().setup(filters)
      if not inSimulation():
         rpc = getGlobalRpcClient(source=RpcClientSource.FROM_LINECARD)
         rpc.provisionComplete()
