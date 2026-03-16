
from . import registerParser
from .default import defaultPlatformParser

@registerParser('daemon', parent=defaultPlatformParser,
                help='run arista daemon to monitor the hardware')
def daemonParser(parser):
   parser.add_argument('-f', '--feature', action='append',
      help='Name of the features to run, default all')
