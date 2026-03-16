
from .. import registerParser
from ..diag import addDiagCommonParser
from ..platform import platformParser

@registerParser('diag', parent=platformParser,
                help='dump diag information for the platform')
def diagParser(parser):
   addDiagCommonParser(parser)
