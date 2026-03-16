
from .. import registerParser
from . import chassisParser

@registerParser('setup', parent=chassisParser,
                help='setup drivers for this platform')
def setupParser(parser):
   pass
