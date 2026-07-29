from enum import Enum

class ReloadCauseAltSource(Enum):
   # The CPU main hardware controller
   CPU = 'CPU'

class ReloadCausePriority(object):
   NONE = 0
   LOW = 10
   NORMAL = 20
   HIGH = 30

   PRIMARY = 0
   SECONDARY = 1

   # All priorities defined above will be eventually cleared out
   # All below priorities will be set a bit weirdly high before the cleanup
   # Priorities will be used in two ways:
   # 1) Specify the significance of providers
   # Any new priority value related to providers should be in [10, 50]
   PREREBOOT = 23
   HARDWARE_MAIN = 22
   HARDWARE_SECONDARY = 21
   # Final values:
   # PREREBOOT = 40
   # HARDWARE_MAIN = 30
   # HARDWARE_SECONDARY = 20
   # 2) Specify the importancy of reload causes from the same provider, majorly
   # between detailed causes and undetailed/unknown ones
   # Any new priority value related to entries should be in [0, 9]
   UNKNOWN = 19
   # Final values: using the duplicated definition above before the cleanup
   # HIGH = 9
   # NORMAL = 5
   # LOW = 1
   # UNKNOWN = 0

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
   EXPANSION_CARD = 'expansion-card'
   SWITCH_CARD = 'switch-card'
   FAN_CARD = 'fan-card'
   LEAK_ROPE_FAIL = 'leak-rope-fail'
   LEAK_DETECTED = 'leak-detected'
   RMC_REBOOT = 'rmcReboot'

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
      EXPANSION_CARD: 'Expansion card fault',
      SWITCH_CARD: 'Switch card fault',
      FAN_CARD: 'Fan card fault',
      LEAK_ROPE_FAIL: 'No rope or rope broken',
      LEAK_DETECTED: 'Leak detected',
      RMC_REBOOT: 'Rebooted by RMC',
   }

   Priority = ReloadCausePriority

   def __init__(self, code, typ, description=None,
                priority=ReloadCausePriority.NORMAL,
                altSource=None):
      self.code = code
      self.typ = typ
      self.description = self.DEFAULT_DESCRIPTIONS.get(typ, str(typ))
      self.priority = priority
      self.altSource = altSource
      if description is not None:
         self.description = f'{self.description} - {description}'
