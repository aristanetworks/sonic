
from .. import registerParser
from ..common import addPriorityArgs
from . import linecardParser

from ....core.provision import ProvisionMode

@registerParser('setup', parent=linecardParser)
def setupParser(parser):
   addPriorityArgs(parser)
   parser.add_argument('--on', action='store_true',
      help='turn on linecard')
   parser.add_argument('--lcpu', action='store_true', default=None,
      help='activate linecard cpu mode when possible')
   parser.add_argument('--provision', type=lambda mode: ProvisionMode[mode.upper()],
                       choices=list(ProvisionMode), default=None,
                       help='set the provision mode')
   parser.add_argument('--powerCycleIfOn', action='store_true',
      help='power cycle the linecard if already on')
