
from .. import registerParser
from ..common import addPriorityArgs
from . import fabricParser

@registerParser('setup', parent=fabricParser)
def setupParser(parser):
   addPriorityArgs(parser)
   parser.add_argument('--on', action='store_true',
      help='turn on fabric card')
   parser.add_argument('--powerCycleIfOn', action='store_true',
      help='power cycle the fabric if already on')
