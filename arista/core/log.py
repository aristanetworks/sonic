import logging
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL
import logging.handlers
import os
import re
import sys

IO = 5

logLevelDict = {
   'IO': IO,
   'DEBUG': DEBUG,
   'INFO': INFO,
   'WARNING': WARNING,
   'ERROR': ERROR,
   'CRITICAL': CRITICAL,
}

dateFmt = '%Y-%m-%d %H:%M:%S'

class LoggerError(Exception):
   def __init__(self, msg, code=1):
      self.code = code
      self.msg = msg

   def __str__(self):
      return 'LoggerError: %s (code %d)' % (self.msg, self.code)

CYAN = "0;36"
PURPLE = "0;35"
BOLD_BLUE = "1;34"
BOLD_YELLOW = "1;32"
BOLD_RED = "1;31"
BOLD_WHITE_ON_RED = "1;37;41"

class ColorFormatter(logging.Formatter):
   COLORS = {
       IO: CYAN,
       DEBUG: PURPLE,
       INFO: BOLD_BLUE,
       WARNING: BOLD_YELLOW,
       ERROR: BOLD_RED,
       CRITICAL: BOLD_WHITE_ON_RED,
   }

   def formatMessage(self, record):
      # NOTE: this will only work with python3, python2 does have this method
      color = "\x1b[%sm" % self.COLORS[record.levelno]
      reset = "\x1b[0m"
      return '%s%s%s' % (color, self._style.format(record), reset)

class LoggerManager(object):
   def __init__(self):
      self.cliVerbosityDict = {}
      self.logfile = None
      self.syslog = False
      self.color = False
      self.loggers = {}

   def initLogger(self, logger, cliLevel, syslogLevel):
      # Prevent the logger from going through its parent handlers.
      # Parents are automatically assigned due to the use of __name__.
      # We should probably only create the handlers on the root parser and
      # write a custom Filter object per logger instead.
      logger.propagate = False

      logger.setLevel(IO)
      if cliLevel:
         color = os.isatty(sys.stdout.fileno()) and self.color
         fmtCls = ColorFormatter if color else logging.Formatter
         logOut = logging.StreamHandler(sys.stdout)
         logOut.setFormatter(fmtCls('%(levelname)s: %(message)s'))
         logOut.setLevel(cliLevel)
         logger.addHandler(logOut)
      else:
         # Ensure that we have at least one handler
         logger.addHandler(logging.NullHandler())

      if self.logfile:
         logFile = logging.FileHandler(self.logfile)
         logFile.setFormatter(logging.Formatter(
               '%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
               datefmt=dateFmt))
         logFile.setLevel(IO)
         logger.addHandler(logFile)

      if self.syslog:
         logSys = logging.handlers.SysLogHandler()
         # format to rfc5424 format
         logSys.setFormatter(
               logging.Formatter('{} arista: %(message)s'.format(getHostname())))
         logSys.setLevel(syslogLevel)
         logger.addHandler(logSys)

      return logger

   def newLogger(self, name, cliLevel=INFO, syslogLevel=WARNING):
      if name.startswith('arista.'):
         name = name[len('arista.'):]

      logger = self.loggers.get(name)
      if logger is not None:
         return logger

      # If a verbosity parameter is given, use it to find the cli log level
      # Otherwise, use the default level
      if self.cliVerbosityDict:
         for pattern, level in self.cliVerbosityDict.items():
            if re.match(pattern, name):
               # level can be None when using verbosity 'abc'
               # Use default level in this case
               if level:
                  cliLevel = level
               break
         else:
            cliLevel = None

      logger = logging.getLogger(name)
      if logger not in self.loggers.values():
         self.initLogger(logger, cliLevel, syslogLevel)
         self.loggers[name] = logger
      return logger

class Logger(object):
   def __init__(self, name, cliLevel=INFO, syslogLevel=WARNING):
      self.name = name
      self.cliLevel = cliLevel
      self.syslogLevel = syslogLevel
      self.logger = None

   def _maybeCreateLogger(self):
      if not self.logger:
         self.logger = loggerManager.newLogger(self.name,
                                               self.cliLevel,
                                               self.syslogLevel)

   def log(self, level, msg, *args, **kwargs):
      self._maybeCreateLogger()
      self.logger.log(level, msg, *args, **kwargs)

   def io(self, msg, *args, **kwargs):
      self.log(IO, msg, *args, **kwargs)

   def debug(self, msg, *args, **kwargs):
      self.log(DEBUG, msg, *args, **kwargs)

   def info(self, msg, *args, **kwargs):
      self.log(INFO, msg, *args, **kwargs)

   def warning(self, msg, *args, **kwargs):
      self.log(WARNING, msg, *args, **kwargs)

   def warn(self, msg, *args, **kwargs):
      self.log(WARNING, msg, *args, **kwargs)

   def error(self, msg, *args, **kwargs):
      self.log(ERROR, msg, *args, **kwargs)

   def exception(self, msg, *args, **kwargs):
      self._maybeCreateLogger()
      self.logger.exception(msg, *args, **kwargs)

def getLogger(name, cliLevel=INFO, syslogLevel=WARNING):
   return Logger(name, cliLevel=cliLevel, syslogLevel=syslogLevel)

def setupLogging(verbosity=None, logfile=None, syslog=False, color=False):
   logging.addLevelName(IO, 'IO')
   loggerManager.cliVerbosityDict = parseVerbosity(verbosity)
   loggerManager.logfile = logfile
   loggerManager.syslog = syslog
   loggerManager.color = color

def parseVerbosity(verbosity):
   verbosityDict = {}

   if not verbosity:
      return verbosityDict

   # Log levels are seperated by ','
   # Each element can be 'abc' (default level is used) or 'abc/LEVEL'
   # It is also possible to use a python regex, e.g. 'ab.' or 'ab./LEVEL'

   for el in verbosity.split(','):
      pattern = el
      logLevel = None

      if el.count('/') > 1:
         raise LoggerError('Invalid verbosity argument')
      elif el.count('/') == 1:
         pattern, logLevelStr = el.split('/')
         if logLevelStr not in logLevelDict:
            raise LoggerError('Invalid log level: %s' % logLevelStr)
         logLevel = logLevelDict[ logLevelStr ]

      try:
         verbosityDict[re.compile(pattern)] = logLevel
      except re.error as e:
         raise LoggerError('Invalid verbosity: %s' % str(e))

   return verbosityDict

loggerManager = LoggerManager()

def getHostname():
   import socket
   try:
      return socket.gethostname()
   except OSError:
      return 'localhost'

