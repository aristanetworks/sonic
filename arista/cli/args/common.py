
def addPriorityArgs(parser):
   parser.add_argument('--early', action='store_true',
      help='perform early initialisation, tied to the switch chip')
   parser.add_argument('--late', action='store_true',
      help='perform late initialisation, tied to the platform')

