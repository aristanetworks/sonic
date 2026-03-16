
from .. import registerParser
from . import fabricParser

@registerParser('clean', parent=fabricParser)
def cleanParser(parser):
   parser.add_argument('-r', '--reset', action='store_true',
      help='put devices in reset before cleanup')
   parser.add_argument('--off', action='store_true',
      help='power off the fabric card')
