
class ReloadCausePriority(object):
   NONE = 0
   LOW = 10
   NORMAL = 20
   HIGH = 30

   PRIMARY = 0
   SECONDARY = 1

class ReloadCauseScore(object):
   # DO NOT CHANGE EXISTING VALUES UNLESS YOU UNDERSTAND THE IMPLICATIONS
   # format:
   # 0:7 -> priority
   UNKNOWN = 0
   DETAILED = (1 << 10)
   EVENT = (1 << 16)
   LOGGED = (1 << 32)

   @staticmethod
   def getPriority(value):
      assert value == (value & 0xff)
      return value & 0xff

class ReloadCauseDesc(object):

   UNKNOWN = 'unknown'
   KILLSWITCH = 'killswitch'
   OVERTEMP = 'overtemp'
   CPU_OVERTEMP = 'cpu-overtemp'
   POWERLOSS = 'powerloss'
   RAIL = 'rail'
   REBOOT = 'reboot'
   BUTTON = 'button'
   WATCHDOG = 'watchdog'
   CPU = 'cpu'
   CPU_S3 = 'cpu-s3'
   CPU_S5 = 'cpu-s5'
   SEU = 'seu'
   NOFANS = 'no-fans'

   DEFAULT_DESCRIPTIONS = {
      UNKNOWN: 'Unknown',
      KILLSWITCH: 'Kill switch',
      OVERTEMP: 'Thermal trip fault',
      POWERLOSS: 'System lost power',
      RAIL: 'Rail fault',
      REBOOT: 'Rebooted by user',
      BUTTON: 'Rebooted by button',
      WATCHDOG: 'Watchdog fired',
      CPU: 'CPU fault',
      CPU_S3: 'CPU state S3',
      CPU_S5: 'CPU state S5',
      SEU: 'SEU fault',
      NOFANS: 'No Fans fault',
   }

   Priority = ReloadCausePriority

   def __init__(self, code, typ, description=None,
                priority=ReloadCausePriority.NORMAL):
      self.code = code
      self.typ = typ
      self.description = self.DEFAULT_DESCRIPTIONS.get(typ, str(typ))
      self.priority = priority
      if description is not None:
         self.description = f'{self.description} - {description}'
