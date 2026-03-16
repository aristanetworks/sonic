
from . import registerParser
from .default import defaultPlatformParser

@registerParser('reset', parent=defaultPlatformParser,
                help='put devices in or out reset')
def resetParser(parser):
   parser.add_argument('device', nargs='*',
      help='device(s) to put in or out of reset')
   parser.add_argument('-t', '--toggle', action='store_true', dest='reset_toggle',
      help='put devices in and out of reset')
   parser.add_argument('-i', '--in', action='store_true', dest='reset_in',
      help='put devices in reset')
   parser.add_argument('-o', '--out', action='store_true', dest='reset_out',
      help='put devices out of reset')
   parser.add_argument('-d', '--delay', type=int, default=1, dest='reset_delay',
      help='time to wait between in and out in seconds')
   parser.add_argument('-l', '--list', action='store_true', dest='reset_list',
      help='list devices that support reset')
