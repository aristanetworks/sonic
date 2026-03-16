
from .. import registerParser
from . import linecardParser

@registerParser('clean', parent=linecardParser)
def cleanParser(parser):
   parser.add_argument('-r', '--reset', action='store_true',
      help='put devices in reset before cleanup')
   parser.add_argument('--off', action='store_true',
      help='power off the fabric card')
   parser.add_argument('--lcpu', action='store_true', default=None,
      help='clean linecard cpu mode when possible')
