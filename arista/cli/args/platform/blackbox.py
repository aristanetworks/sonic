
from __future__ import absolute_import, division, print_function

from .. import registerParser
from ..platform import platformParser

@registerParser('blackbox', parent=platformParser,
                help='configure the hardware blackbox')
def blackboxParser(parser):
   parser = parser.add_mutually_exclusive_group(required=True)
   parser.add_argument('--enable', action='store_true', dest='blackbox_enable',
      help='start blackbox logging')
   parser.add_argument('--disable', action='store_false', dest='blackbox_enable',
      help='stop blackbox logging')
