
from __future__ import absolute_import, division, print_function

try:
   import asyncio
except ImportError:
   # This file shouldn't be packaged for python2 but just in case
   print('This feature only works in python3')
   raise

from .log import getLogger

logging = getLogger(__name__)

_features = {}

class DaemonFeature(object):
   NAME = None

   def __init__(self):
      self.daemon = None

   def attachToDaemon(self, daemon):
      self.daemon = daemon

   def init(self):
      raise NotImplementedError

   def __str__(self):
      return 'DaemonFeature(%s)' % self.NAME

   @classmethod
   def runnable(cls, daemon):
      return True

class PollDaemonFeature(DaemonFeature):
   INTERVAL = 1.

   def init(self):
      self.daemon.loop.create_task(self._callback())

   async def _callback(self):
      last = self.daemon.loop.time()
      while True:
         now = self.daemon.loop.time()
         try:
            self.callback(now - last)
         except Exception:  # pylint: disable=broad-except
            logging.debug('%s raised exception', self.NAME, exc_info=True)
         last = now
         await asyncio.sleep(self.INTERVAL)

   def callback(self, elapsed):
      raise NotImplementedError

class OneShotFeature(DaemonFeature):
   def init(self):
      self.run()

   def run(self):
      raise NotImplementedError

class Daemon(object):
   def __init__(self, platform):
      self.platform = platform
      self.features = []
      self.loop = asyncio.get_event_loop()

   def addFeature(self, feature):
      self.features.append(feature)

   def run(self):
      for feature in self.features:
         logging.info('daemon: initializing feature %s', feature)
         feature.attachToDaemon(self)
         try:
            feature.init()
         except Exception as e:  # pylint: disable=broad-except
            logging.error('daemon: failed to initialize feature %s', feature)
            logging.error('%s', e)

      logging.info('deamon: running event loop')
      try:
         self.loop.run_forever()
      finally:
         logging.info('daemon: terminating')
         self.loop.close()
         logging.info('daemon: done')

def registerDaemonFeature():
   def wrapper(cls):
      assert cls.NAME, \
         'DaemonFeature %s needs a NAME' % cls
      assert cls.NAME not in _features, \
         'A feature named %s already exists' % cls.NAME
      assert issubclass(cls, DaemonFeature)
      _features[cls.NAME] = cls
      return cls
   return wrapper

def getDaemonFeatureCls(enableNames, skipNames):
   from .. import daemon as _

   if not enableNames and not skipNames:
      return _features.values()

   names = enableNames or _features.keys()
   if skipNames:
      names = set(names) - set(skipNames)

   features = []
   for name in names:
      featureCls = _features.get(name)
      assert featureCls is not None
      features.append(featureCls)

   return features
