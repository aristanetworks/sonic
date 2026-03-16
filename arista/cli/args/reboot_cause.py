
from . import registerParser
from .default import defaultPlatformParser

@registerParser('reboot-cause', parent=defaultPlatformParser,
                help='reload cause information',
                description='''
Read last reboot information from the hardware and display it.
''')
def rebootCauseParser(parser):
   parser.add_argument('--history', action='store_true',
      help='print reboot causes history if it exists')
   parser.add_argument('--process', action='store_true',
      help='process last reboot cause and generate report (do not use)')
