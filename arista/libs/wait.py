import time

from .python import monotonicRaw

class TimeoutError(Exception):
   def __init__(self, msg, code=1):
      self.msg = msg
      self.code = code

   def __str__(self):
      return 'TimeoutError: %s (code %d)' % (self.msg, self.code)

def waitFor(func, description=None, timeout=60, delay=None, delayMax=1000,
            delayFactor=2, interval=None, wait=None, args=None, kwargs=None):
   '''Run func and return if it's True. Otherwise, exit after timeout seconds.
      Inputs: timeout: in seconds
              description: printed out if timeout occurs
              interval: interval of time between attempts in ms
              delay: initial interval of time between attempts in ms
              delayFactor: factor for the exponential backoff
              delayMax: maximum of time between attempts in ms
              wait: time to wait before running the loop
              args and kwargs: are inputs for func
      Outputs: the output of func if it's done, othewise False.
   '''
   assert delay is None or interval is None, "choose one or the other"
   assert delay is None or delay > 0
   assert interval is None or interval > 0

   args = args or ()
   kwargs = kwargs or {}

   def _nowMsecs():
      return int(round(monotonicRaw() * 1000))

   start = _nowMsecs()
   end = start + timeout * 1000

   if wait is not None:
      time.sleep(wait / 1000)

   while True:
      result = func(*args, **kwargs)
      if result:
         return result

      now = _nowMsecs()
      if now > end:
         if not description:
            description = func.__name__
         raise TimeoutError("Timed out waiting for %s" % description)

      stime = None
      if interval is not None:
         stime = interval
      elif delay is not None:
         delay = min(delay * delayFactor, delayMax)
         stime = delay

      if stime is not None:
         if now + stime > end:
            stime = end - now
         time.sleep(stime / 1000)

   raise RuntimeError("Not reachable")
