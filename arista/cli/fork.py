import os

from ..core.log import getLogger, getLoggerManager

from .exception import ActionComplete

logging = getLogger(__name__)

def processIterParentWait(collection):
   """The collection needs to be an iterable"""

   pids = []

   for item in collection:
      pid = os.fork()
      if pid == 0:
         logging.debug('[child %s] starting for %s...', os.getpid(), item)
         getLoggerManager().setPrefix('%s: ' % item)
         # NOTE: once in the fork, yield the item and stop the iteration
         #       it means that each item in the for loop will be executed in a
         #       different process.
         yield item
         return

      pids.append(pid)

   # wait for processes to finish
   for pid in pids:
      logging.debug('[parent] waiting for child %d', pid)
      os.waitpid(pid, 0)

   logging.debug('[parent] all children completed')

   # the main process doesn't do anything
   raise ActionComplete
