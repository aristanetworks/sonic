from enum import Enum
import inspect

# pylint: disable=import-error
from swsscommon import swsscommon
# pylint: disable=import-error
from sonic_py_common import multi_asic

from ..core.log import getLogger, setupLogging
from ..libs.python import monotonicRaw

setupLogging(verbosity='.*/NOTICE', syslog=True)
logging = getLogger(__name__)

class GlobalLuxteraReset:
   def __init__(self):
      self.stateDb = None
      self.statePortTable = None
      self.configPortTable = None

      self.luxteraResetSm = {}
      self.stateDb = {}
      self.statePortTable = {}
      self.configDb = {}
      self.configPortTable = {}

      self.portMapping = None
      self.physicalToNamespace = None
      self.configDbByAsic = {}
      self.loadPortTable()
      self.initializeDb()

   def getLogicalPortName(self, slotNum):
      if not self.portMapping:
         return ""
      return self.portMapping[str(slotNum)]

   def getStateDb(self, slotNum, attr):
      namespace = self.physicalToNamespace[str(slotNum)]
      return self.statePortTable[namespace].hget(
                self.getLogicalPortName(slotNum), attr)[1]

   def getConfigDb(self, slotNum, attr):
      namespace = self.physicalToNamespace[str(slotNum)]
      return self.configPortTable[namespace].hget(
                self.getLogicalPortName(slotNum), attr)[1]

   def initializeDb(self):
      namespaces = multi_asic.get_front_end_namespaces()

      for namespace in namespaces:
         self.stateDb[namespace] = swsscommon.DBConnector("STATE_DB", 0, False,
                                                          namespace)
         self.statePortTable[namespace] = swsscommon.Table(self.stateDb[namespace],
                                                           "PORT_TABLE")
         self.configPortTable[namespace] = swsscommon.Table(self.configDb[namespace],
                                                            "PORT")

   def loadPortTable(self):
      if self.portMapping:
         return
      swsscommon.SonicDBConfig.initializeGlobalConfig()
      namespaces = multi_asic.get_front_end_namespaces()
      physicalToLogical = {}
      physicalToNamespace = {}
      for namespace in namespaces:
         self.configDb[namespace] = swsscommon.DBConnector(
            "CONFIG_DB", 0, False, namespace)
         configPortTable = swsscommon.Table(self.configDb[namespace], "PORT")
         keys = configPortTable.getKeys()

         for key in keys:
            index = configPortTable.hget(key, "index")[1]
            physicalToLogical[index] = key
            physicalToNamespace[index] = namespace

      self.portMapping = physicalToLogical
      self.physicalToNamespace = physicalToNamespace

   def getResetSm(self, sfp):
      luxteraResetSm = LuxteraResetSm(sfp, self)
      self.luxteraResetSm[sfp.get_id()] = luxteraResetSm
      return luxteraResetSm

class LuxteraResetSm:
   AFFECTED_PSM4_MODULES = [
      # Model Name Prefix, Manufacturer Name Prefix
      ("QSFP-100G-PSM4", "Arista Networks"),
      ("LUXN2604BO", "LUXTERA"),
      ("LUX42604BO", "LUXTERA"),
      ("LUX42604CO", "LUXTERA")
   ]

   STATE = Enum("State", "NA WAIT_HOST_TX RESETIN RESETOUT COMPLETE RETRY")
   DOWN = "down"
   UP = "up"
   HOST_IS_READY = "true"

   RESET_DURATION = 2.2
   LINK_UP_TIMEOUT = 60

   def __init__(self, sfp, globalReset):
      self.sfp = sfp
      self.slotNum = sfp.get_id()
      self.slot = sfp._slot
      self.globalReset = globalReset

      self.state = self.STATE.NA
      self.adminStatus = self.DOWN
      self.linkStatus = self.UP
      self.presence = True
      self.lastUpdate = monotonicRaw()

      self.portMapping = {}
      self.physicalToNamespace = {}
      self.configDbByAsic = {}

      # Attributes to cache
      self._isAffectedPsm4 = None
      self._vendorName = None
      self._vendorPn = None
      self._initialized = False
      self._hwsku = None

      self.cleanup()

   def isAffectedPsm4(self):
      if self._isAffectedPsm4 is not None:
         return self._isAffectedPsm4

      xcvrModel, xcvrManufacturer = self.getModuleInfo()
      if xcvrModel is None and xcvrManufacturer is None:
         return False

      for module in self.AFFECTED_PSM4_MODULES:
         if module[0] in xcvrModel and module[1] in xcvrManufacturer:
            self._isAffectedPsm4  = True
            return True

      self._isAffectedPsm4  = False
      return False

   def cleanup(self):
      self.state = self.STATE.NA
      self.adminStatus = self.DOWN
      self.linkStatus = self.UP
      self.presence = True
      self.lastUpdate = monotonicRaw()

      self.portMapping = {}
      self.physicalToNamespace = {}
      self.configDbByAsic = {}

      # Attributes to cache
      self._isAffectedPsm4 = None
      self._vendorName = None
      self._vendorPn = None
      self._initialized = False
      self._hwsku = None

   def getModuleInfo(self):
      if not self.slot.slot.presentGpio.isActive():
         return None, None

      if self._vendorName and self._vendorPn:
         return self._vendorName, self._vendorPn

      vendorName = None
      vendorPn = None

      try:
         self.slot.slot.resetOut()
         xcvrInfo = self.sfp.get_transceiver_info()
      except Exception as e: # pylint: disable=broad-except
         logging.notice(
            f"LuxteraResetSm: Failed to get Xcvr information from slot "\
            f"{self.slotNum} {e}")

      if xcvrInfo:
         vendorPn = xcvrInfo.get("manufacturer")
         vendorName = xcvrInfo.get("model")
         self._vendorName = vendorName
         self._vendorPn = vendorPn

      return vendorName, vendorPn

   def initialize(self):
      if not self._initialized:
         try:
            self._initialized = True
         except: # pylint: disable=bare-except
            logging.notice(f"LuxteraResetSm: Failed to initialize database for "\
                           f"slot {self.slotNum}")

   def runSm(self):
      if not self._initialized:
         self.initialize()

      adminStatus = self.globalReset.getConfigDb(self.slotNum, "admin_status")
      hostTxReady = self.globalReset.getStateDb(self.slotNum, "host_tx_ready")
      linkStatus = self.globalReset.getStateDb(self.slotNum, "netdev_oper_status")

      # True when adminStatus transitions from DOWN to UP
      adminStatusChanged = adminStatus == self.UP and self.adminStatus == self.DOWN
      # True when linkStatus transitions from UP to DOWN
      linkStatusChanged = linkStatus == self.DOWN and self.linkStatus == self.UP

      if ((adminStatusChanged) or
           self.state == self.STATE.RETRY or
           linkStatusChanged):
         self.lastUpdate = monotonicRaw()
         self.slot.slot.reset.resetIn()
         self.presence = False
         self.state = self.STATE.WAIT_HOST_TX

      elif (self.state == self.STATE.WAIT_HOST_TX and
             hostTxReady == self.HOST_IS_READY):
         self.state = self.STATE.RESETIN

      elif (self.state == self.STATE.RESETIN and
            monotonicRaw() - self.lastUpdate > self.RESET_DURATION):
         logging.notice(f"LuxteraResetSm: Resetting Slot {self.slotNum}")
         self.slot.slot.reset.resetOut()
         self.lastUpdate = monotonicRaw()
         self.presence = True
         self.state = self.STATE.RESETOUT

      elif self.state == self.STATE.RESETOUT:
         if linkStatus == self.UP:
            self.state = self.STATE.COMPLETE
         elif monotonicRaw() - self.lastUpdate >  self.LINK_UP_TIMEOUT:
            logging.notice(f"LuxteraResetSm: Retrying Slot {self.slotNum}")
            self.state = self.STATE.RETRY

      self.adminStatus = adminStatus
      self.linkStatus = linkStatus

      return self.presence

   def isCalledFromPollEvents(self):
      frame = inspect.currentframe()
      while frame:
         if frame.f_code.co_name == "poll_events":
            return True
         frame = frame.f_back
      return False

   def maybeRunResetSm(self, presence):
      if not presence and self.isAffectedPsm4() is not None:
         self.cleanup()
      elif self.isAffectedPsm4() and self.isCalledFromPollEvents():
         presence = self.runSm()

      return presence

def getLuxteraResetSm(sfp):
   return LuxteraResetSm(sfp, sfp.globalLuxteraReset)
