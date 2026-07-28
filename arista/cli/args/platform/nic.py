
from .. import registerParser
from ..platform import platformParser

@registerParser('nic', parent=platformParser,
                help='NIC interface configuration')
def nicParser(parser):
   parser = parser.add_mutually_exclusive_group(required=True)
   parser.add_argument('--config', action='store_true',
      help='configure NIC interfaces')
   parser.add_argument('--clean', action='store_true',
      help='unconfigure NIC interfaces')
