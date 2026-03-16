
from . import registerParser
from .default import defaultPlatformParser

@registerParser('reboot', parent=defaultPlatformParser,
                help='perform a cold reboot for platform',
                description='''
Powercycle the switch by cutting power to all components.
The behavior of such reboot differ from a regular CPU reset.
''')
def rebootParser(parser):
   pass
