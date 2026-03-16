from .. import registerParser
from ..diag import addDiagCommonParser
from ..fabric import fabricParser

@registerParser('diag', parent=fabricParser,
                help='dump diag information for fabrics')
def diagParser(parser):
   addDiagCommonParser(parser)
