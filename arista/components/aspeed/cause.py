
from ...core.cause import (
   ReloadCauseEntry,
   HardwareReloadCauseProvider,
   ReloadCauseScore,
)
from ...core.log import getLogger

from ...descs.cause import ReloadCauseDesc, ReloadCausePriority

logging = getLogger(__name__)

class AspeedReloadCauseProvider(HardwareReloadCauseProvider):

   def __init__(self, regs, **kwargs):
      super().__init__(**kwargs)
      self.regs = regs

   def __str__(self):
      return self.__class__.__name__

   def process(self):
      causes = []

      if self.regs.pwrst():
         logging.debug('power-on reset detected, clearing PWRST# bit')
         self.regs.pwrst(1)
         causes.append(ReloadCauseEntry(
            cause=ReloadCauseDesc.POWERLOSS.typ,
            rcDesc='Power loss detected via SCU0_050 PWRST#',
            score=ReloadCauseScore.LOGGED | ReloadCauseScore.DETAILED |
                  ReloadCauseScore.getPriority(ReloadCausePriority.NORMAL),
            priority=ReloadCausePriority.NORMAL,
         ))

      # future: additional SCU register checks
      # future: causes.extend(self._parseCmdlineCauses())

      self.causes = causes
