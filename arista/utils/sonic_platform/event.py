
import select
import time

from arista.core.config import Config

REMOVED = 0
INSERTED = 1
I2C_BUS_STUCK = 2
BAD_EEPROM = 3
UNSUPPORTED_CABLE = 4
HIGH_TEMPERATURE = 5
BAD_CABLE = 6

class Event(object):
   def __init__(self, uid, obj, typ):
      self.uid = uid
      self.obj = obj
      self.typ = typ
      self.status = None

   def get_status_changed(self):
      # NOTE: The logic in this function could be enhanced to report more
      #       statuses. This would would then require object specific logic
      status = INSERTED if self.obj.get_presence() else REMOVED
      changed = (status != self.status and self.status is not None)
      self.status = status
      return changed, self.status

class EpollEvent(Event):
   def __init__(self, uid, obj, typ, intrf):
      super(EpollEvent, self).__init__(uid, obj, typ)
      self.intrf = intrf
      self.fd_ = None
      self.status = None

   def fd(self):
      if not self.fd_:
         self.fd_ = open(self.intrf)
      return self.fd_.fileno()

   def refd(self):
      self.close()
      return self.fd()

   def close(self):
      if self.fd_ is not None:
         self.fd_.close()
         self.fd_ = None

   def clear(self):
      self.obj.clear_interrupt()

class PollEvent(Event):
   pass

class EventWatcher(object):
   def __init__(self, preserve=False, pollInterval=1000.):
      self.preserve = preserve
      self.pollInterval = pollInterval
      self.epollHack = True
      self.epoll_ = None
      self.pollItems = {}
      self.epollItems = {}
      self.epollFds = {}
      self.keys = set()

   @property
   def epoll(self):
      if self.epoll_ is None or self.epoll_.closed:
         self.epoll_ = select.epoll()
      return self.epoll_

   def load_item(self, name, uid, item):
      if self.preserve:
         if item in self.pollItems or item in self.epollItems:
            return

      intrf = item.get_interrupt_file()
      if intrf and Config().api_event_use_interrupts:
         event = EpollEvent(uid, item, name, intrf)
         event.clear()
         self.epollItems[item] = event
         self.epollFds[event.fd()] = event
         self.epoll.register(event.fd(), select.EPOLLIN)
      else:
         event = PollEvent(uid, item, name)
         self.pollItems[item] = event

      # first time initialization
      event.get_status_changed()

   def load(self, collections):
      self.keys |= set(collections.keys())
      for name, col in collections.items():
         for uid, item in enumerate(col or [], 1 if name == 'sfp' else 0):
            self.load_item(name, uid, item)

   def get_empty_results(self):
      return { k : {} for k in self.keys }

   def process_epoll_events(self, events, res):
      detected = False
      for (fd, _) in events:
         event = self.epollFds[fd]
         changed, status = event.get_status_changed()
         if changed:
            res[event.typ][str(event.uid)] = str(status)
            detected = True

         event.clear()

         if self.epollHack:
            self.epoll.unregister(fd)
            del self.epollFds[fd]
            self.epoll.register(event.refd(), select.EPOLLIN)
            self.epollFds[event.fd()] = event

      return detected

   def poll_events(self, res):
      detected = False
      for event in self.pollItems.values():
         try:
            changed, status = event.get_status_changed()
         except Exception: # pylint: disable=broad-except
            continue
         if changed:
            res[event.typ][str(event.uid)] = str(status)
            detected = True
      return detected

   def teardown(self):
      if self.preserve:
         return

      for item in self.epollItems.values():
         item.close()
      self.epoll.close()

   def wait(self, timeout=0):
      res = self.get_empty_results()
      block = (timeout == 0)
      detected = False

      while not detected and (timeout > 0 or block):
         begin = time.time()
         interval = self.pollInterval if block else min(timeout, self.pollInterval)

         try:
            events = self.epoll.poll(interval / 1000.)
            if events:
               detected |= self.process_epoll_events(events, res)
         except select.error:
            pass

         detected |= self.poll_events(res)

         elapsed = time.time() - begin
         timeout -= elapsed * 1000

      self.teardown()

      return res
