import datetime
import random

import pytest

from ....core.inventory import Inventory
from ....core.tests.helpers import (
   classname,
   getAllSystems,
)
from ....descs.cause import ReloadCauseDesc, CauseDesc, ReloadCausePriority
from ....descs.rail import RailDesc
from ....drivers.dpm.ucd import UcdUserDriver
from ....libs.date import datetimeToStr
from ....tests.logging import getLogger
from ..ucd import (
   Ucd,
   Ucd90320,
   UcdGpi,
   UcdMon,
   UcdReloadCauseEntry,
   UcdReloadCauseProvider,
)

validCauseDesc = [value for value in vars(ReloadCauseDesc).values()
                  if isinstance(value, CauseDesc)]

@pytest.mark.parametrize("platform", getAllSystems(), ids=classname)
def testUcdGpiTypeCheck(platform):

   validValues = [value.typ for value in validCauseDesc]

   rcProviders = platform.getInventory().getReloadCauseProviders()

   errors = []
   def checkCauses(ucd):
      for cause in ucd.causes:
         assert isinstance(cause, (UcdGpi, UcdMon))
         if cause.causeDesc.typ not in validValues:
            errors.append(f"Reload cause name '{cause.causeDesc.typ}' on "
                          f"{platform} is not valid.")
         if isinstance(cause, UcdMon) and cause.bit >= ucd.PAGE_COUNT:
            errors.append(f"UcdMon cause '{cause.causeDesc.typ}' has an invalid "
                          f"page number {cause.bit} while maximum page number "
                          f"allowed on {ucd.__class__.__name__} is {ucd.PAGE_COUNT}."
                         )
   for rcp in rcProviders:
      if isinstance(rcp, UcdReloadCauseProvider):
         checkCauses(rcp.ucd)

   if errors:
      errorMsg = "\n".join(errors)
      pytest.fail(f"UcdGpi reload cause name validation failed\n"
                  f"{errorMsg}\nAllowed values from "
                  f"class ReloadCauseDesc: {validValues}")

@pytest.fixture(scope="class")
def logger(request):
   request.cls.logger = getLogger(request.cls.__name__)
   yield

class MockUcdDriver(UcdUserDriver):

   def __init__(self, **kwargs):
      super().__init__(**kwargs)
      self.block = {
         self.registers.LOGGED_FAULTS : [0] * self.registers.LOGGED_FAULTS_COUNT,
         self.registers.LOGGED_FAULT_DETAIL_INDEX : 0x0,
         self.registers.LOGGED_FAULT_DETAIL : {},
      }

   def getVersion(self):
      return "SERIAL UCDMOC 2.3.4.0005 241218"

   def readFaults(self):
      return self.block[self.registers.LOGGED_FAULTS]

   def clearFaults(self):
      pass

   def getFaultCount(self):
      return self.block[self.registers.LOGGED_FAULT_DETAIL_INDEX]

   def getFaultNum(self, num):
      if num not in self.block[self.registers.LOGGED_FAULT_DETAIL]:
         self.block[self.registers.LOGGED_FAULT_DETAIL][num] = (
            [0] * self.registers.LOGGED_FAULT_DETAIL_COUNT)
      return self.block[self.registers.LOGGED_FAULT_DETAIL][num]

   def _dataFeeder(self, reg, data, num=None):
      if reg == self.registers.LOGGED_FAULT_DETAIL:
         if num is not None:
            self.block[reg][num] = data
      else:
         self.block[reg] = data

   def setSimpleFaults(self, data):
      self._dataFeeder(self.registers.LOGGED_FAULTS, data)

   def setDetailedFaultCount(self, data):
      self._dataFeeder(self.registers.LOGGED_FAULT_DETAIL_INDEX, data)

   def setDetailedFault(self, num, data):
      self._dataFeeder(self.registers.LOGGED_FAULT_DETAIL, data, num=num)

ucdClasses = Ucd.__subclasses__()
ucdGpiClsMap = [
   (gpiNum, ucdCls)
   for ucdCls in ucdClasses
   for gpiNum in range(1, ucdCls.gpiSize * 8 + 1)
]
ucdPagedFaults = [
   (paged, typ, Ucd.FAULTS.get((paged, typ)))
   for paged, typ in Ucd.FAULTS.keys()
]

@pytest.mark.usefixtures("logger")
class TestUcdCause:
   # This is applied as timestamp of all detailed faults
   FAULT_MSEC_BASE = datetime.timedelta(
      hours=12, minutes=34, seconds=56, milliseconds=789)
   FAULT_DAYS_BASE = 1
   # We don't provide fault value in the cause, set to 0 for all faults
   FAULT_VALUE_BASE = 0

   @pytest.fixture(autouse=True)
   def setup(self):
      Ucd.DRIVER = MockUcdDriver
      yield
      Ucd.DRIVER = UcdUserDriver

   def _assertEqual(self, name, val, exp):
      assert val == exp, f"{name}: Expected {exp}, got {val}"

   def _assertCauseEqual(self, cause, expectedCause):
      if not cause and not expectedCause:
         # No cause is found as expected
         return
      assert cause and expectedCause, "One of the cause is none."
      self._assertEqual("cause", cause.cause, expectedCause.cause)
      self._assertEqual("time", cause.time, expectedCause.time)
      self._assertEqual("description", cause.description, expectedCause.description)
      self._assertEqual("priority", cause.priority, expectedCause.priority)
      self._assertEqual("altSource", cause.altSource, expectedCause.altSource)

   def _encodeDetailedFaultReg(self, ucdCls, paged, ftype, page):
      reg = [0] * 10
      timestamp = int(self.FAULT_MSEC_BASE.total_seconds() * 1000)
      days = self.FAULT_DAYS_BASE
      if ucdCls is Ucd90320:
         reg[0] = (((page - 1) & 0x1f) << 3) | ((timestamp >> 24) & 0x7)
         reg[1] = (timestamp >> 16) & 0xff
         reg[2] = (timestamp >> 8) & 0xff
         reg[3] = timestamp & 0xff
         reg[4] = (((paged & 0x1) << 7) |
                   ((ftype & 0xf) << 3) |
                   ((days >> 13) & 0x7))
         reg[5] = (days >> 5) & 0xff
         reg[6] = (days & 0x1f) << 3
         reg.extend([0, 0])
      else:
         reg[0] = (timestamp >> 24) & 0xff
         reg[1] = (timestamp >> 16) & 0xff
         reg[2] = (timestamp >> 8) & 0xff
         reg[3] = timestamp & 0xff
         reg[4] = (((paged & 0x1) << 7) |
                   ((ftype & 0xf) << 3) |
                   (((page - 1) >> 1) & 0x7))
         reg[5] = (((page - 1) & 0x1) << 7) | ((days >> 16) & 0x7f)
         reg[6] = (days >> 8) & 0xff
         reg[7] = days & 0xff
      return reg

   def testDebugInfoSimpleFaults(self):
      # Simple-fault entries should carry the LOGGED_FAULTS bitmap in debugInfo,
      # formatted as space-separated hex bytes.
      ucd = Ucd(inventory=Inventory())
      # Bit 2 in the npf byte = resequence-error
      reg = [0x04, 0x00]
      ucd.driver.setSimpleFaults(reg)
      causes = ucd.getReloadCauses(False)
      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      assert causes[0].debugInfo == '04 00'

   def testDebugInfoDetailedFaults(self):
      # Detailed-fault entries should carry their own LOGGED_FAULT_DETAIL block.
      ucd = Ucd(inventory=Inventory())
      debugInfo = '02 b3 2c 95 48 00 00 01 00 00'
      reg = [int(b, 16) for b in debugInfo.split()]
      ucd.driver.setDetailedFaultCount(1)
      ucd.driver.setDetailedFault(0, reg)
      causes = ucd.getReloadCauses(False)
      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      assert causes[0].debugInfo == debugInfo

   @pytest.mark.parametrize("bitNum", [2, 3])
   @pytest.mark.parametrize("ucdCls", ucdClasses)
   @pytest.mark.parametrize("noiseBit", [0, 1, 4, 5, 6, 7])
   def testNpfFaults(self, bitNum, ucdCls, noiseBit):
      # Generate the correct answer first
      fault = ucdCls.FAULTS.get((False, bitNum))
      # If the chip model does not support npf
      # Also fix npf size to 1 as no model use more than 1 byte so we don't know
      # the format if we have multiple bytes of npf
      if ucdCls.npfSize != 1:
         return
      expectedCause = UcdReloadCauseEntry(
         cause=fault.getReason(), rcDesc='non paged fault')
      # Struct the ucd component
      ucd = ucdCls(inventory=Inventory())
      reg = [(0x1 << bitNum) + (0x1 << noiseBit)]
      ucd.driver.setSimpleFaults(reg)
      causes = ucd.getReloadCauses(False)
      # Test is considered successful if:
      # * The expected cause is found
      # * No other cause is found
      self.logger.debug(f"Get {len(causes)} causes: "
                        " ".join([str(cause) for cause in causes]))
      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      self._assertCauseEqual(causes[0], expectedCause)

   @pytest.mark.parametrize("gpiNum, ucdCls", ucdGpiClsMap)
   @pytest.mark.parametrize("causeDesc", [None] + validCauseDesc)
   def testGpiFaults(self, gpiNum, ucdCls, causeDesc):
      # Build the gpi cause
      gpiCause = UcdGpi(gpiNum, causeDesc) if causeDesc else None
      # Generate the correct cause
      expectedCause = UcdReloadCauseEntry(
         cause=gpiCause.causeDesc.typ if gpiCause else f'gpi-{gpiNum}',
         rcDesc=gpiCause.getReason(page=gpiNum) if gpiCause else 'unknown gpi fault',
         priority=gpiCause.priority if gpiCause else ReloadCausePriority.UNKNOWN
      )
      # Struct the ucd component
      ucd = ucdCls(causes=[gpiCause] if gpiCause else None, inventory=Inventory())
      bytePos = (gpiNum - 1) // 8 + ucdCls.npfSize
      bitPos = (gpiNum - 1) % 8
      reg = [0] * bytePos + [(0x1 << bitPos)]
      ucd.driver.setSimpleFaults(reg)
      causes = ucd.getReloadCauses(False)
      # Test is considered successful if:
      # * The expected cause is found
      # * No other cause is found
      self.logger.debug(f"Get {len(causes)} causes: "
                        " ".join([str(cause) for cause in causes]))
      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      self._assertCauseEqual(causes[0], expectedCause)

   @pytest.mark.parametrize("gpiCount, ucdCls",
                            [(count, ucdCls)
                             for ucdCls in ucdClasses
                             for count in range(2, ucdCls.gpiSize * 8 + 1)])
   def testMultipleGpiFaults(self, gpiCount, ucdCls):
      # Select the causes randomly and use gpi number linearly as base case already
      # tested in testGpiFaults
      # Build the expected cause
      gpiCauses = []
      expectedCauses = []
      regValue = 0
      causeDescPool = [None] + validCauseDesc
      for gpiNum in range(1, gpiCount):
         regValue = (regValue << 1) + 0x1
         causeDesc = random.choice(causeDescPool)
         gpiCause = UcdGpi(gpiNum, causeDesc) if causeDesc else None
         if gpiCause is not None:
            gpiCauses.append(gpiCause)
         expectedCause = UcdReloadCauseEntry(
            cause=gpiCause.causeDesc.typ if gpiCause else f'gpi-{gpiNum}',
            rcDesc=(gpiCause.getReason(page=gpiNum)
                    if gpiCause else 'unknown gpi fault'),
            priority=gpiCause.priority if gpiCause else ReloadCausePriority.UNKNOWN
         )
         expectedCauses.append(expectedCause)
      # Struct the ucd component
      ucd = ucdCls(causes=gpiCauses, inventory=Inventory())
      reg = [0] * ucdCls.npfSize
      for _ in range(ucdCls.gpiSize):
         reg += [regValue & 0xff]
         regValue >>= 8
      ucd.driver.setSimpleFaults(reg)
      causes = ucd.getReloadCauses(False)
      # Test is considered successful if:
      # * The expected amount of causes is found
      # * All causes found match, this is in-place for simple gpi faults
      self.logger.debug(f"Get {len(causes)} causes: "
                        " ".join([str(cause) for cause in causes]))
      assert len(causes) == len(expectedCauses), (
         f"Expected {len(expectedCauses)} cause(s), get {len(causes)}")
      for cause, expectedCause in zip(causes, expectedCauses):
         self._assertCauseEqual(cause, expectedCause)

   @pytest.mark.parametrize("gpiNum, ucdCls", ucdGpiClsMap)
   @pytest.mark.parametrize("causeDesc", [None] + validCauseDesc)
   def testDetailedGpiFaults(self, gpiNum, ucdCls, causeDesc):
      # Build the gpi cause
      gpiCause = UcdGpi(gpiNum, causeDesc) if causeDesc else None
      # Generate the correct cause
      expectedCause = UcdReloadCauseEntry(
         cause=gpiCause.causeDesc.typ if gpiCause else f'gpi-{gpiNum}',
         rcTime=datetimeToStr(ucdCls.faultTimeBase +
                              datetime.timedelta(days=self.FAULT_DAYS_BASE) +
                              self.FAULT_MSEC_BASE),
         rcDesc=gpiCause.getReason(page=gpiNum, detailed=True) if gpiCause else (
            f'gpi {gpiNum} detailed fault'),
         priority=gpiCause.priority if gpiCause else ReloadCausePriority.UNKNOWN,
         altSource=gpiCause.altSource if gpiCause else None,
      )
      # Struct the ucd component
      ucd = ucdCls(causes=[gpiCause] if gpiCause else None, inventory=Inventory())
      reg = self._encodeDetailedFaultReg(ucdCls, 0, 9, gpiNum)
      ucd.driver.setDetailedFaultCount(1)
      ucd.driver.setDetailedFault(0, reg)
      causes = ucd.getReloadCauses(False)
      # Test is considered successful if:
      # * The expected cause is found
      # * No other cause is found
      self.logger.debug(f"Get {len(causes)} causes: "
                        " ".join([str(cause) for cause in causes]))
      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      self._assertCauseEqual(causes[0], expectedCause)

   @pytest.mark.parametrize("monType", [0, 1] )
   @pytest.mark.parametrize("ucdCls", ucdClasses)
   # Testing all fault descs, while I believe only powerloss, uv and ov are supported
   @pytest.mark.parametrize("causeDesc", [None] + validCauseDesc)
   def testDetailedMonFaults(self, monType, ucdCls, causeDesc):
      # No need to test all mon pages, set default to 1
      monPage = 1
      # Build the mon cause
      monCause = UcdMon(monPage, causeDesc) if causeDesc else None
      # Get the corresponding paged fault
      pagedFault = ucdCls.FAULTS.get((True, monType))
      # Generate the correct cause
      causeName = monCause.causeDesc.typ if monCause else pagedFault.description
      causeDesc = monCause.getReason(page=monPage, detailed=True) if monCause else (
         pagedFault.getReason(page=monPage))
      expectedCause = UcdReloadCauseEntry(
         cause=causeName,
         rcTime=datetimeToStr(ucdCls.faultTimeBase +
                              datetime.timedelta(days=self.FAULT_DAYS_BASE) +
                              self.FAULT_MSEC_BASE),
         rcDesc=causeDesc,
         priority=monCause.priority if monCause else ReloadCausePriority.UNKNOWN,
         altSource=monCause.altSource if monCause else None,
      )
      # Struct the ucd component
      ucd = ucdCls(causes=[monCause] if monCause else None, inventory=Inventory())
      reg = self._encodeDetailedFaultReg(ucdCls, 1, monType, monPage)
      ucd.driver.setDetailedFaultCount(1)
      ucd.driver.setDetailedFault(0, reg)
      causes = ucd.getReloadCauses(False)
      # Test is considered successful if:
      # * The expected cause is found
      # * No other cause is found
      self.logger.debug(f"Get {len(causes)} causes: "
                        " ".join([str(cause) for cause in causes]))
      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      self._assertCauseEqual(causes[0], expectedCause)

   # Add a fan fault that we don't record to the test
   @pytest.mark.parametrize("paged, ftype, faultDesc",
                            [(False, 8, None)] + ucdPagedFaults)
   @pytest.mark.parametrize("ucdCls", ucdClasses)
   def testDetailedPagedFaults(self, paged, ftype, faultDesc, ucdCls):
      # Fix page 1 to be hit
      faultPage = 1
      # Generate the correct cause
      expectedCause = None
      if faultDesc:
         expectedCause = UcdReloadCauseEntry(
            cause=faultDesc.description,
            rcTime=datetimeToStr(ucdCls.faultTimeBase +
                                 datetime.timedelta(days=self.FAULT_DAYS_BASE) +
                                 self.FAULT_MSEC_BASE),
            rcDesc=faultDesc.getReason(page=faultPage),
            priority=ReloadCausePriority.UNKNOWN,
         )
      # Struct the ucd component
      ucd = ucdCls(inventory=Inventory())
      reg = self._encodeDetailedFaultReg(ucdCls, paged, ftype, faultPage)
      ucd.driver.setDetailedFaultCount(1)
      ucd.driver.setDetailedFault(0, reg)
      causes = ucd.getReloadCauses(False)
      # Test is considered successful if:
      # * The expected cause is found
      # * No other cause is found
      self.logger.debug(f"Get {len(causes)} causes: "
                        " ".join([str(cause) for cause in causes]))
      if expectedCause is None:
         assert len(causes) == 0, f"Expected no cause, get {len(causes)}"
         return
      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      self._assertCauseEqual(causes[0], expectedCause)

   def testGetReloadCauseDescsIncludesFaultRails(self):
      ucd = Ucd(
         inventory=Inventory(),
         causes=[UcdGpi(1, ReloadCauseDesc.REBOOT)],
         rails=[
            RailDesc(railId=2, name='P1V0_SWITCH'),
            RailDesc(railId=3, name='P1V8_SERDES'),
         ],
      )
      provider = ucd.inventory.getReloadCauseProviders()[0]
      descs = provider.getReloadCauseDescs()

      assert len(descs) == 3
      self._assertEqual("code", descs[1].codeStr, 'rail2')
      self._assertEqual("type", descs[1].typ, 'rail')
      self._assertEqual(
         "description", descs[1].description, 'Rail fault - P1V0_SWITCH')
      self._assertEqual("code", descs[2].codeStr, 'rail3')
      self._assertEqual(
         "description", descs[2].description, 'Rail fault - P1V8_SERDES')

   def testDetailedPagedFaultUsesRailName(self):
      faultPage = 2
      railName = 'P1V0_SWITCH'
      ucd = Ucd(
         inventory=Inventory(),
         rails=[RailDesc(railId=faultPage, name=railName)],
      )
      reg = self._encodeDetailedFaultReg(Ucd, 1, 1, faultPage)
      ucd.driver.setDetailedFaultCount(1)
      ucd.driver.setDetailedFault(0, reg)

      causes = ucd.getReloadCauses(False)

      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      self._assertEqual(
         "description",
         causes[0].description,
         f'under-voltage on rail {faultPage} - {railName}',
      )

   def testDetailedPagedFaultWithoutRailNameKeepsOldFormat(self):
      faultPage = 2
      ucd = Ucd(
         inventory=Inventory(),
         rails=[RailDesc(railId=1, name='P3V3_ALW')],
      )
      reg = self._encodeDetailedFaultReg(Ucd, 1, 1, faultPage)
      ucd.driver.setDetailedFaultCount(1)
      ucd.driver.setDetailedFault(0, reg)

      causes = ucd.getReloadCauses(False)

      assert len(causes) == 1, f"Expected one cause, get {len(causes)}"
      self._assertEqual(
         "description",
         causes[0].description,
         f'under-voltage on rail {faultPage}',
      )

   # Test complex cases:
   # * if all faults are logged up to the storage limit
   # * if simple faults are covered by their detailed versions
   # * if simple faults come after detailed faults
   # * if non-unknown simple faults are logged for ignored detailed faults due to
   # storage limit
   # For easiness of testing, make the test majorly based on Ucd, with an option to
   # add one Mon 1 on powerloss
   @pytest.mark.parametrize("faultCount, ucdCls", [
      (count, ucdCls)
      for ucdCls in ucdClasses
      for count in range(2, ucdCls.Registers.LOGGED_FAULT_DETAIL_COUNT + 5)
      if ucdCls.gpiSize != 0])
   @pytest.mark.parametrize("hasUcdMon", [True, False])
   @pytest.mark.parametrize("hasSimpleFault", [True, False])
   def testMultipleDetailedFaults(
      self, faultCount, ucdCls, hasUcdMon, hasSimpleFault):
      # Select the causes randomly
      # Build the expected cause
      ucdCauses = {}
      expectedCauses = []
      reg = []
      # Handle mon first so that it can be logged for sure
      if hasUcdMon:
         monPage = 1
         causeDesc = ReloadCauseDesc.POWERLOSS
         monCause = UcdMon(monPage, causeDesc)
         ucdCauses["mon"] = monCause
         # Get the undervoltage paged fault for powerloss
         pagedFault = ucdCls.FAULTS.get((True, 1))
         # Generate the correct cause
         causeName = monCause.causeDesc.typ if monCause else pagedFault.description
         causeDesc = (
            monCause.getReason(page=monPage, detailed=True)
            if monCause else pagedFault.getReason(page=monPage))
         expectedCauses.append(UcdReloadCauseEntry(
            cause=causeName,
            rcTime=datetimeToStr(ucdCls.faultTimeBase +
                                 datetime.timedelta(days=self.FAULT_DAYS_BASE) +
                                 self.FAULT_MSEC_BASE),
            rcDesc=causeDesc,
            priority=monCause.priority if monCause else ReloadCausePriority.UNKNOWN,
            altSource=monCause.altSource if monCause else None,
            ))
         reg.append(self._encodeDetailedFaultReg(ucdCls, 1, 1, monPage))
      # Generate the gpi faults
      # GPI1 will not have detailed fault
      # GPI2 will surely appear to be a detailed fault that gets ignored if we logged
      # more than the storage limit
      # GPI3 will surely have at least one detailed fault
      # Other gpi detailed faults are randomly selected, each can have multi-entries
      # All GPIs will have corresponding simple faults if enabled
      causeDescPool = [None] + validCauseDesc
      gpiNumList = [3] + random.choices(
         range(3, ucdCls.gpiSize * 8 + 1), k=(faultCount - 1 - len(reg)))
      if faultCount > ucdCls.Registers.LOGGED_FAULT_DETAIL_COUNT:
         gpiNumList[-1] = 2
      ucdGpiDescMap = random.choices(causeDescPool, k=(ucdCls.gpiSize * 8))
      detailedGpiList = set()
      for gpiNum in gpiNumList:
         causeDesc = ucdGpiDescMap[gpiNum - 1]
         # Build the gpi cause
         gpiCause = UcdGpi(gpiNum, causeDesc) if causeDesc else None
         if gpiCause is not None and gpiNum not in ucdCauses:
            ucdCauses[gpiNum] = gpiCause
         # Generate the correct cause
         if len(expectedCauses) < ucdCls.Registers.LOGGED_FAULT_DETAIL_COUNT:
            detailedGpiList.add(gpiNum)
            expectedCauses.append(UcdReloadCauseEntry(
               cause=gpiCause.causeDesc.typ if gpiCause else f'gpi-{gpiNum}',
               rcTime=datetimeToStr(ucdCls.faultTimeBase +
                                    datetime.timedelta(days=self.FAULT_DAYS_BASE) +
                                    self.FAULT_MSEC_BASE),
               rcDesc=(
                  gpiCause.getReason(page=gpiNum, detailed=True) if gpiCause else (
                     f'gpi {gpiNum} detailed fault')),
               priority=(
                  gpiCause.priority if gpiCause else ReloadCausePriority.UNKNOWN),
               altSource=gpiCause.altSource if gpiCause else None,
            ))
         reg.append(self._encodeDetailedFaultReg(ucdCls, 0, 9, gpiNum))
      # Struct the ucd component
      ucd = ucdCls(causes=list(ucdCauses.values()), inventory=Inventory())
      # If simple faults are enabled, struct them
      if hasSimpleFault:
         # Construct the reg value
         simpleFaultReg = [0] * ucdCls.npfSize
         for _ in range(ucdCls.gpiSize):
            simpleFaultReg += [0xff]
         ucd.driver.setSimpleFaults(simpleFaultReg)
         # Check if simple fault should be in the result
         for gpiNum in sorted(
            set(range(1, ucdCls.gpiSize * 8 + 1)) - detailedGpiList):
            gpiCause = ucdCauses.get(gpiNum)
            expectedCauses.append(UcdReloadCauseEntry(
               cause=gpiCause.causeDesc.typ if gpiCause else f'gpi-{gpiNum}',
               rcDesc=(gpiCause.getReason(page=gpiNum)
                       if gpiCause else 'unknown gpi fault'),
               priority=(
                  gpiCause.priority if gpiCause else ReloadCausePriority.UNKNOWN)
            ))
      expectedCount = min(faultCount, ucdCls.Registers.LOGGED_FAULT_DETAIL_COUNT)
      ucd.driver.setDetailedFaultCount(expectedCount)
      for index, regVal in enumerate(reg):
         ucd.driver.setDetailedFault(index, regVal)
      causes = ucd.getReloadCauses(False)
      # Test is considered successful if:
      # * The expected amount of causes is found
      # * All causes found match, in-place
      # * Causes out of record size are omitted
      self.logger.debug(f"Get {len(causes)} causes: "
                        " ".join([str(cause) for cause in causes]))
      assert len(causes) == len(expectedCauses), (
         f"Expected {len(expectedCauses)} causes, get {len(causes)}")
      for cause, expectedCause in zip(causes, expectedCauses):
         self._assertCauseEqual(cause, expectedCause)
