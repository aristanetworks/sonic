import datetime
import os
import re
import sys
import syslog
import traceback

class TraceLevel(object):
   def __init__(self, level, name, syslog, color):
      self.level = level
      self.name = name
      self.syslog = syslog
      self.color = color

CYAN = "0;36"
PURPLE = "0;35"
BOLD_RED = "1;31"
BOLD_GREEN = "1;32"
BOLD_YELLOW = "1;33"
BOLD_BLUE = "1;34"
BOLD_CYAN = "1;36"
BOLD_WHITE_ON_RED = "1;37;41"

LEVELS = [
   TraceLevel(0, 'CRITICAL', syslog.LOG_CRIT, BOLD_WHITE_ON_RED),
   TraceLevel(1, 'ERROR', syslog.LOG_ERR, BOLD_RED),
   TraceLevel(2, 'WARNING', syslog.LOG_WARNING, BOLD_YELLOW),
   TraceLevel(3, 'NOTICE', syslog.LOG_NOTICE, BOLD_CYAN),
   TraceLevel(4, 'INFO', syslog.LOG_INFO, BOLD_BLUE),
   TraceLevel(5, 'DEBUG', syslog.LOG_DEBUG, CYAN),
   TraceLevel(6, 'IO', None, PURPLE),
]
NAME_TO_LEVEL = { t.name : t.level for t in LEVELS }
for lvl in LEVELS:
   setattr(sys.modules[__name__], lvl.name, lvl.level)

DATE_FMT = '%Y-%m-%d %H:%M:%S.%f'

class LoggerError(Exception):
   def __init__(self, msg, code=1):
      self.code = code
      self.msg = msg

   def __str__(self):
      return 'LoggerError: %s (code %d)' % (self.msg, self.code)

class Logger(object):
   def __init__(self, manager, name, cliLevel=None, syslogLevel=None):
      self.manager = manager
      self.name = name
      self.levels = {}

   def log(self, level, msg, *args, **kwargs):
      record = LogRecord(self, LEVELS[level], msg, *args, **kwargs)
      self.manager.log(record)

   def io(self, msg, *args, **kwargs):
      self.log(IO, msg, *args, **kwargs)

   def debug(self, msg, *args, **kwargs):
      self.log(DEBUG, msg, *args, **kwargs)

   def info(self, msg, *args, **kwargs):
      self.log(INFO, msg, *args, **kwargs)

   def notice(self, msg, *args, **kwargs):
      self.log(NOTICE, msg, *args, **kwargs)

   def warning(self, msg, *args, **kwargs):
      self.log(WARNING, msg, *args, **kwargs)

   def error(self, msg, *args, **kwargs):
      self.log(ERROR, msg, *args, **kwargs)

   def exception(self, msg, *args, **kwargs):
      kwargs.setdefault('exc', True)
      self.log(ERROR, msg, *args, **kwargs)

class LogRecord(object):
   def __init__(self, logger, level, msg, *args, **kwargs):
      self.logger = logger
      self.msg = msg
      self.level = level
      self.args = args
      self.exc = kwargs.get('exc', False)
      self.kwargs = kwargs
      self.time = datetime.datetime.now()
      self._data = None

   @property
   def data(self):
      if self._data is None:
         self._data = self.render()
      return self._data

   def render(self):
      return str(self.msg) % self.args

class LogSink(object):
   NAME = None
   def __init__(self, manager, verbosity, level, fmt):
      self.manager = manager
      self.verbosity = verbosity
      self.level = level
      self.fmt = fmt

   def matchLoggerLevel(self, name, defaultLevel):
      for pattern, level in self.verbosity.items():
         if level and re.match(pattern, name):
            return level
      return defaultLevel

   def applyLoggerLevel(self, name, logger):
      level = logger.levels.get(self.NAME, self.level)
      logger.levels[self.NAME] = self.matchLoggerLevel(name, level)

   def applyLoggerLevels(self, loggers):
      for name, logger in loggers.items():
         self.applyLoggerLevel(name, logger)

   def getLoggerLevel(self, record):
      return record.logger.levels[self.NAME]

   def isEnabledFor(self, record):
      level = self.getLoggerLevel(record) or self.level
      return record.level.level <= level

   def write(self, line, record):
      raise NotImplementedError

   def formatMessage(self, record):
      return self.fmt % {
         'prefix': self.manager.prefix,
         'message': record.data,
         'time': record.time.strftime(DATE_FMT),
         'levelname': record.level.name,
      }

   def log(self, record):
      if not self.isEnabledFor(record):
         return
      line = self.formatMessage(record)
      self.write(line, record)

class CliLogSink(LogSink):
   NAME = 'cli'
   def __init__(self, manager, verbosity, level, fmt, color):
      super(CliLogSink, self).__init__(manager, verbosity, level, fmt)
      self.color = color

   def formatMessage(self, record):
      message = super(CliLogSink, self).formatMessage(record)
      if not self.color:
         return message
      color = "\x1b[%sm" % record.level.color
      reset = "\x1b[0m"
      return '%s%s%s' % (color, message, reset)

   def write(self, line, record):
      print(line)
      if record.exc:
         traceback.print_exception(*sys.exc_info())

class FileLogSink(LogSink):
   NAME = 'file'
   def __init__(self, manager, verbosity, level, fmt, logfile):
      super(FileLogSink, self).__init__(manager, verbosity, level, fmt)
      self.logfile = logfile
      self.file = open(logfile, 'a', buffering=1)

   def write(self, line, record):
      try:
         self.file.write(line + '\n')
         if record.exc:
            lines = traceback.format_exception(*sys.exc_info())
            self.file.write(''.join(lines))
      except Exception: # pylint: disable=broad-except
         pass # ignore errors like disk full

class SyslogLogSink(LogSink):
   NAME = 'syslog'
   def __init__(self, manager, verbosity, level, fmt):
      super(SyslogLogSink, self).__init__(manager, verbosity, level, fmt)
      syslog.openlog(
         logoption=syslog.LOG_PID | syslog.LOG_NDELAY,
         facility=syslog.LOG_DAEMON,
      )

   def write(self, line, record):
      if not record.level.syslog:
         return
      syslog.syslog(record.level.syslog, line)

class LoggerManager(object):
   def __init__(self):
      self.color = False
      self.prefix = ''
      self.loggers = {}
      self.defaultLevel = {}
      self.verbosity = {}
      self.sinks = []

   def log(self, record):
      for sink in self.sinks:
         sink.log(record)

   def setPrefix(self, prefix):
      self.prefix = prefix

   def addSink(self, sink):
      sink.applyLoggerLevels(self.loggers)
      self.sinks.append(sink)

   def initCliLogging(self, verbosity, default=INFO, color=False):
      fmt = '%(prefix)s%(levelname)s: %(message)s'
      sink = CliLogSink(self, verbosity, default, fmt, color)
      self.addSink(sink)

   def initSyslogLogging(self, verbosity, default=NOTICE):
      fmt = '%(prefix)s%(message)s'
      sink = SyslogLogSink(self, verbosity, default, fmt)
      self.addSink(sink)

   def initFileLogging(self, logfile, verbosity, default=IO):
      fmt = '%(time)s %(prefix)s%(levelname)s: %(message)s'
      sink = FileLogSink(self, verbosity, default, fmt, logfile)
      self.addSink(sink)

   def newLogger(self, name):
      if name.startswith('arista.'):
         name = name[len('arista.'):]

      logger = self.loggers.get(name)
      if logger is not None:
         return logger

      logger = Logger(self, name)
      for sink in self.sinks:
         sink.applyLoggerLevel(name, logger)
      self.loggers[name] = logger

      return logger

def getLogger(name):
   return getLoggerManager().newLogger(name)

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
         if logLevelStr not in NAME_TO_LEVEL:
            raise LoggerError('Invalid log level: %s' % logLevelStr)
         logLevel = NAME_TO_LEVEL[logLevelStr]

      try:
         verbosityDict[re.compile(pattern)] = logLevel
      except re.error as e:
         raise LoggerError('Invalid verbosity: %s' % str(e))

   return verbosityDict

_loggerManager = None
def getLoggerManager():
   global _loggerManager
   if _loggerManager is None:
      _loggerManager = LoggerManager()
   return _loggerManager

def setupLogging(verbosity=None, logfile=None, logfileVerbosity=None,
                 syslog=False, syslogVerbosity=None, color=False):
   lm = getLoggerManager()
   lm.initCliLogging(parseVerbosity(verbosity), color=color)
   if logfile:
      lm.initFileLogging(logfile, parseVerbosity(logfileVerbosity))
   if syslog:
      lm.initSyslogLogging(parseVerbosity(syslogVerbosity))

getLoggerManager()
