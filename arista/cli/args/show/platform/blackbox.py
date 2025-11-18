
from . import registerParser, showPlatformParser

@registerParser('blackbox', parent=showPlatformParser,
                help='Show platform blackbox status')
def showPlatformBlackBoxParser(_parser):
   pass
