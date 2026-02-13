
from . import registerParser, showPlatformParser

@registerParser('blackbox', parent=showPlatformParser,
                help='Show platform blackbox status')
def showPlatformBlackBoxParser(parser):
   parser.add_argument('path', nargs='?', default=None,
      help='blackbox log file to decode (default: latest)')
   parser.add_argument('-a', '--all', action='store_true',
      dest='blackbox_show_all',
      help='decode all stored blackbox logs')
