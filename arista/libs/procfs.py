
import datetime
import os
import time

from .fs import readFileContent

from ..core.log import getLogger

logging = getLogger(__name__)

def uptime(path='/proc/uptime'):
   '''Read uptime from /proc/uptime'''
   try:
      return tuple(float(v) for v in readFileContent(path).rstrip().split())
   except IOError:
      # NOTE: This codepath should only be reached during testing in environments
      #       where the procfs is not reachable.
      return (float(time.time()), float(time.time()))

def bootDatetime():
   '''Read uptime and return a datetime object representing boot time'''
   return datetime.datetime.now() - datetime.timedelta(seconds=uptime()[0])

cmdlineDict = {}
def getCmdlineDict(path='/proc/cmdline'):
   global cmdlineDict # pylint: disable=global-statement

   if cmdlineDict:
      return cmdlineDict

   data = {}

   # The machine running the pytest may not have this path, or permission
   try:
      with open(path, encoding='utf8') as f:
         for entry in f.read().split():
            idx = entry.find('=')
            if idx == -1:
               data[entry] = None
            else:
               data[entry[:idx]] = entry[idx+1:]
   except IOError:
      logging.error("%s is not available, the Arista library may not work properly.",
                    path)

   cmdlineDict = data
   return data

def inKdump(path='/proc/vmcore'):
   return os.path.exists(path)
