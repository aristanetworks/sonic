
from .. import registerParser
from ..default import defaultPlatformParser

@registerParser('platform', parent=defaultPlatformParser,
                help='Platform related features')
def platformParser(parser):
   pass
