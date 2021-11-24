#!/usr/bin/env python

from __future__ import print_function, with_statement

import argparse
import tempfile
import time
import sys
import os

# NOTE: This import comes first as it initializes the logging infrastructure
from ..core.log import setupLogging, getLogger, LoggerError

from .parser import CliContext, ActionError
from .args import getRootParser, registerParser
from .actions import registerAction

from .. import platforms

from ..core import utils
from ..core.config import Config
from ..core.backtrace import loadBacktraceHook
from ..core.version import getVersionInfo

logging = getLogger(__name__)

class HelpAllAction(argparse._HelpAction):
   # pylint: disable=protected-access
   def _printUsage(self, parser):
      usage = parser.format_usage()
      usage = ' '.join(l.strip() for l in usage.splitlines())
      print(usage[7:])

   def _printParser(self, parser):
      self._printUsage(parser)
      subparsers_actions = [
          action for action in parser._actions
          if isinstance(action, argparse._SubParsersAction)
      ]

      for subparsers_action in subparsers_actions:
         for subparser in subparsers_action.choices.values():
            self._printParser(subparser)

   def __call__(self, parser, namespace, values, option_string=None):
      self._printParser(parser)
      parser.exit()

def setupSimulation():
   utils.simulation = True
   assert utils.inSimulation()

   logging.info('Running in simulation mode')
   Config().lock_file = tempfile.mktemp(prefix='arista-', suffix='.lock')

def addCommonArgs(parser):
   parser.add_argument('-v', '--verbosity', type=str,
                       help='set verbosity')

def rootParser(parser):
   parser.add_argument('-p', '--platform', type=str,
                       help='name of the platform to load')
   parser.add_argument('-l', '--logfile', type=str,
                       help='log file to log to')
   parser.add_argument('--logfile-verbosity',
                       help='verbosity level for logfile output')
   parser.add_argument('-s', '--simulation', action='store_true',
                       help='force simulation mode')
   parser.add_argument('--syslog', action='store_true',
                       help='also send logs to syslog')
   parser.add_argument('--syslog-verbosity',
                       help='verbosity level for syslog messages')
   parser.add_argument('--color', action='store_true',
                       help='color logs during an interactive session')
   parser.add_argument('--help-all', action=HelpAllAction,
                       help='display all available clis')
   addCommonArgs(parser)

def parseArgs(args):
   parser = argparse.ArgumentParser(
      description='Arista platform management framework',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter
   )

   rootParser(parser)

   root = getRootParser()
   root.addSubparsers(parser, common=addCommonArgs)

   args = parser.parse_args(args)
   if args.action is None or args.action == 'help':
      parser.print_help()
      sys.exit(0)

   return root, args

def main(args):
   root, args = parseArgs(args)

   try:
      setupLogging(
         verbosity=args.verbosity,
         logfile=args.logfile,
         logfileVerbosity=args.logfile_verbosity,
         syslog=args.syslog,
         syslogVerbosity=args.syslog_verbosity,
         color=args.color,
      )
   except LoggerError as e:
      print(e.msg)
      return e.code

   if args.verbosity:
      loadBacktraceHook()

   if args.simulation:
      setupSimulation()

   logging.debug(args)
   logging.debug('Library info: %s',
                 ' '.join('%s=%s' % x for x in getVersionInfo().items()))

   try:
      root.runAction(CliContext(), args)
   except ActionError as e:
      logging.error('%s', e)
      return e.code

   return 0
