import time

from .config import Config
from .inventory import ReloadCause
from .utils import JsonStoredData

RELOAD_CAUSE_HISTORY_SIZE=128

class ReloadCauseEntry(ReloadCause):
   def __init__(self, cause='unknown', rcTime='unknown', rcDesc=''):
      self.cause = cause
      self.time = rcTime
      self.description = rcDesc

   def __str__(self):
      items = [self.cause]
      if self.description:
         items.append('description: %s' % self.description)
      if self.time != "unknown":
         items.append('time: %s' % self.time)
      return ', '.join(items)

   def getCause(self):
      return self.cause

   def getDescription(self):
      return self.description

   def getTime(self):
      return self.time

class ReloadCauseDataStore(JsonStoredData):
   def __init__(self, name=Config().reboot_cause_file, **kwargs):
      super(ReloadCauseDataStore, self).__init__(name,**kwargs)
      self.dataType = ReloadCauseEntry

   def convertFormatV1(self, data):
      for item in data:
         item['cause'] = item['reloadReason']
         del item['reloadReason']
      return data

   def maybeConvertReloadCauseFormat(self, data):
      assert isinstance(data, list) # TODO: use a dict to store data in the future
      if data and data[0].get('reloadReason'):
         data = self.convertFormatV1(data)
      return data

   def readCauses(self):
      data = self.maybeConvertReloadCauseFormat(self.read())
      return [self._createObj(item, self.dataType) for item in data]

   def writeCauses(self, causes):
      return self.writeList(causes)

def updateReloadCausesHistory(newCauses):
   rebootCauses = ReloadCauseDataStore(lifespan='persistent')
   causes = []
   if rebootCauses.exist():
      causes = rebootCauses.readCauses()
      for newCause in newCauses:
         addCause = True
         for cause in causes:
            if newCause.getTime() == cause.getTime() and \
                  newCause.getCause() == cause.getCause():
               addCause = False
               break
         if addCause:
            causes.append(newCause)
      rebootCauses.clear()
   else:
      causes = newCauses

   if len(causes) > RELOAD_CAUSE_HISTORY_SIZE:
      causes = causes[len(causes) - RELOAD_CAUSE_HISTORY_SIZE:]

   rebootCauses.writeList(causes)

def getReloadCause():
   rebootCauses = ReloadCauseDataStore()
   if rebootCauses.exist():
      return rebootCauses.readCauses()
   return None

def getReloadCauseHistory():
   rebootCauses = ReloadCauseDataStore(lifespan='persistent')
   if rebootCauses.exist():
      return rebootCauses.readCauses()
   return None

def datetimeToStr(datetime):
   return time.strftime("%Y-%m-%d %H:%M:%S UTC",
                        time.gmtime(time.mktime(datetime.timetuple())))
