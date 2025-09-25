
from .. import registerParser
from ..common import addPriorityArgs
from . import linecardParser

@registerParser('eeprom', parent=linecardParser)
def eepromParser(parser):
   addPriorityArgs(parser)
   parser.add_argument('--reset', action='store_true',
      help='reset eeprom cache for linecard')
