from dataclasses import dataclass
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
   BERT = 19
   # Final values:
   # PREREBOOT = 40
   # HARDWARE_MAIN = 30
   # HARDWARE_SECONDARY = 20
   # BERT = 10
   # 2) Specify the importancy of reload causes from the same provider, majorly
   # between detailed causes and undetailed/unknown ones
   # Any new priority value related to entries should be in [0, 9]
   UNKNOWN = 18
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

@dataclass(frozen=True)
class CauseDesc:
   typ: str
   desc: str

class ReloadCauseDesc(object):

   UNKNOWN = CauseDesc('unknown', 'Unknown')
   KILLSWITCH = CauseDesc('killswitch', 'Kill switch')
   OVERTEMP = CauseDesc('overtemp', 'Thermal trip fault')
   CPU_OVERTEMP = CauseDesc('cpu-overtemp', 'CPU thermal trip fault')
   ASIC_OVERTEMP = CauseDesc('asic-overtemp', 'ASIC thermal trip fault')
   POWERLOSS = CauseDesc('powerloss', 'System lost power')
   RAIL = CauseDesc('rail', 'Rail fault')
   OVER_CURRENT = CauseDesc('over-current', 'Over current fault')
   REBOOT = CauseDesc('reboot', 'Rebooted by user')
   BUTTON = CauseDesc('button', 'Rebooted by button')
   WATCHDOG = CauseDesc('watchdog', 'Watchdog fired')
   CPU = CauseDesc('cpu', 'CPU fault')
   CPU_S3 = CauseDesc('cpu-s3', 'CPU state S3')
   CPU_S5 = CauseDesc('cpu-s5', 'CPU state S5')
   CPU_CATERR = CauseDesc('cpu-caterr', 'CPU CATERR')
   SEU = CauseDesc('seu', 'SEU fault')
   NO_FANS = CauseDesc('no-fans', 'No Fans fault')
   EXPANSION_CARD = CauseDesc('expansion-card', 'Expansion card fault')
   SWITCH_CARD = CauseDesc('switch-card', 'Switch card fault')
   FAN_CARD = CauseDesc('fan-card', 'Fan card fault')
   LEAK_ROPE_FAIL = CauseDesc('leak-rope-fail', 'No rope or rope broken')
   LEAK_DETECTED = CauseDesc('leak-detected', 'Leak detected')
   RMC_REBOOT = CauseDesc('rmc-reboot', 'Rebooted by RMC')

   Priority = ReloadCausePriority

   def __init__(self, code, causedef, description=None,
                priority=ReloadCausePriority.NORMAL,
                altSource=None):
      self.code = code
      self.typ = (
         causedef.typ if isinstance(causedef, CauseDesc) else causedef)
      self.description = (
         causedef.desc if isinstance(causedef, CauseDesc) else str(causedef)
      )
      self.priority = priority
      self.altSource = altSource
      if description is not None:
         self.description = f'{self.description} - {description}'
