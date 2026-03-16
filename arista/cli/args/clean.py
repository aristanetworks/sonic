
from . import registerParser
from .default import defaultPlatformParser

@registerParser('clean', parent=defaultPlatformParser,
                help='unload drivers for this platform')
def cleanParser(parser):
   parser.add_argument('-r', '--reset', action='store_true',
      help='put devices in reset before cleanup')
