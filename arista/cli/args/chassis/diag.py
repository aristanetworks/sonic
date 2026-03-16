
from .. import registerParser
from ..diag import addDiagCommonParser
from ..chassis import chassisParser

@registerParser('diag', parent=chassisParser,
                help='dump diag information for the chassis')
def diagParser(parser):
   addDiagCommonParser(parser)
