
from .config import parseKeyValueConfig

from ..core.config import flashPath

machineConfigDict = {}
def getMachineConfigDict(path=flashPath('machine.conf')):
   global machineConfigDict

   if machineConfigDict:
      return machineConfigDict

   data = {k.split('_', 1)[1] : v for k, v in parseKeyValueConfig(path).items()}
   machineConfigDict = data
   return data
