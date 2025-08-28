from __future__ import absolute_import, division, print_function

from .. import registerParser
from . import uartParser

@registerParser('reset', parent=uartParser)
def resetParser(parser):
   parser.add_argument('-i', '--id', type=int, default=None, action='append',
         help='id of the card to operate on')
