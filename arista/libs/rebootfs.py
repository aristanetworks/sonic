import json

from ..core.utils import FileLock
from ..core.config import Config, flashPath
from ..core.log import getLogger

logging = getLogger(__name__)

REBOOT_CAUSE_FILE = flashPath("reboot-cause/reboot-cause.txt")
LC_REBOOT_INFO_FILE = flashPath("reboot-cause/platform/lc-reboot-info.json")

def writeJsonDataToFile(file, data):
   try:
      with open(file, 'w', encoding='utf-8') as f:
         json.dump(data, f, indent=4, separators=(',', ':'))
   except json.JSONDecodeError as e:
      logging.error('JSON serialization error: %s', e)

def setOsSoftwareRebootCause(description):
   with open(REBOOT_CAUSE_FILE, "w", encoding='utf-8') as f:
      f.write(description)

def getOsSoftwareRebootCause():
   rebootCause = None
   try:
      with open(REBOOT_CAUSE_FILE, 'r', encoding='utf-8') as f:
         rebootCause = f.read()
   except FileNotFoundError:
      logging.error('SW reboot cause file not found')
   return rebootCause

def setAllLcRebootInfo(chassis, rebootCause, version=1):
   writeJsonDataToFile(LC_REBOOT_INFO_FILE, {
      'version' : version,
      'linecards' : {
         str(lc.getSlotId()) : rebootCause
         for lc in chassis.iterLinecards() if lc.getPresence()
      },
   })

def getAndSetLcRebootCause(lc):
   defaultLcRebootCause = 'None'
   lcRebootCause = defaultLcRebootCause
   info = {}
   with FileLock(Config().lock_file, auto_release=True):
      try:
         with open(LC_REBOOT_INFO_FILE, 'r', encoding='utf-8') as f:
            info = json.load(f)
      except FileNotFoundError:
         logging.error("Linecard reboot info file not found")
      except json.JSONDecodeError:
         logging.error("Linecard reboot info file is not in valid JSON format")
      if 'linecards' in info and str(lc.getSlotId()) in info['linecards']:
         lcRebootCause = info['linecards'][str(lc.getSlotId())]
         info['linecards'][str(lc.getSlotId())] = defaultLcRebootCause
      writeJsonDataToFile(LC_REBOOT_INFO_FILE, info)
   return lcRebootCause
