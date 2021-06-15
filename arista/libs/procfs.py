
import datetime
import time

from .fs import readFileContent

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
