import os.path

from .config import parseKeyValueConfig

MACHINE_CONF_PATH = "/host/machine.conf"

machineConfigDict = {}
def getMachineConfigDict(path=MACHINE_CONF_PATH):
   global machineConfigDict

   if machineConfigDict or not os.path.exists(path):
      return machineConfigDict

   data = {k.split('_', 1)[1] : v for k, v in parseKeyValueConfig(path).items()}
   machineConfigDict = data
   return data

def getPlatformName():
   return getMachineConfigDict().get("platform")
