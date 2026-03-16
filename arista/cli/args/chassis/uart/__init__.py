from .. import registerParser, chassisParser

@registerParser('uart', parent=chassisParser,
                help='Serial console related features')
def uartParser(parser): # pylint: disable=unused-argument
   pass
