
from .card import Card
from .provision import ProvisionMode

class LCpuCtx(object):
   def __init__(self, provision=ProvisionMode.NONE):
      self.provision = provision

class Linecard(Card): # pylint: disable=abstract-method
   ABSOLUTE_CARD_OFFSET = 3
