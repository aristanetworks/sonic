
from .. import registerParser
from ..default import defaultPlatformParser

@registerParser('chassis', parent=defaultPlatformParser,
                help='Chassis related features')
def chassisParser(parser):
   pass
