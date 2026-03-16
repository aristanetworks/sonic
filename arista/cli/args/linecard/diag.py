
from .. import registerParser
from ..diag import addDiagCommonParser
from ..linecard import linecardParser

@registerParser('diag', parent=linecardParser,
                help='dump diag information for linecards')
def diagParser(parser):
   addDiagCommonParser(parser)
