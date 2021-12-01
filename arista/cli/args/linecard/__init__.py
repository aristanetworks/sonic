
from __future__ import absolute_import, division, print_function

from .. import registerParser
from ..default import defaultPlatformParser

@registerParser('linecard', parent=defaultPlatformParser,
                help='Linecard related features')
def linecardParser(parser):
   parser.add_argument('-i', '--id', type=int, default=None, action='append',
      help='id of the card to operate on')
   parser.add_argument('--parallel', action='store_true',
      help='run card operations in parallel')
