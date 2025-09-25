
from __future__ import absolute_import, division, print_function

from . import registerParser
from .default import defaultPlatformParser

@registerParser('daemon', parent=defaultPlatformParser,
                help='run arista daemon to monitor the hardware')
def daemonParser(parser):
   group = parser.add_mutually_exclusive_group()
   group.add_argument('-f', '--feature', action='append',
      help='Name of the features to run, default all')
   group.add_argument('-s', '--skip-feature', action='append',
      help='Name of the features to skip, default none')
