
from . import registerParser
from .default import defaultPlatformParser

@registerParser('watchdog', parent=defaultPlatformParser,
                help='configure the hardware watchdog')
def watchdogParser(parser):
   parser = parser.add_mutually_exclusive_group(required=True)
   parser.add_argument('--status', action='store_true', dest='watchdog_status',
      help='print the hardware watchdog status')
   parser.add_argument('--stop', action='store_true', dest='watchdog_stop',
      help='stop the hardware watchdog')
   parser.add_argument('--arm', type=int, nargs='?', dest='watchdog_timeout',
      const=300, help='arm the hardware watchdog for X seconds before it triggers')
