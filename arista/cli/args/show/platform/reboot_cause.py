
from . import registerParser, showPlatformParser

@registerParser('reboot-cause', parent=showPlatformParser,
                help='Show reboot cause info')
def rebootCauseParser(parser):
   parser.add_argument('-a', '--all', action='store_true')
   parser.add_argument('-H', '--history', action='store_true')
   parser.add_argument('-l', '--list', action='store_true',
                       help='List all possible reload causes for this platform')
