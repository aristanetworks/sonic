import os
import subprocess
from unittest.mock import Mock, mock_open, patch

import pytest

from ..driver.kernel import KernelDriver
from .. import prerequisites
from ..driver.kernel.amd_pcie import AmdPcieKernelDriver


def cpuInfo(vendor='AuthenticAMD', family=0x19, model=0x44, flags='fpu sse2'):
   return ('processor\t: 0\n'
           f'vendor_id\t: {vendor}\n'
           f'cpu family\t: {family}\n'
           f'model\t\t: {model}\n'
           'model name\t: AMD processor\n'
           f'flags\t\t: {flags}\n\n')


@pytest.fixture(name='policyDriver')
def policyDriverFixture(tmp_path, monkeypatch):
   monkeypatch.setattr('platform.machine', lambda: 'x86_64')
   monkeypatch.setattr('arista.core.utils.inSimulation', lambda: False)
   (tmp_path / 'profile').write_text('V3000\n', encoding='ascii')
   cpuInfoPath = tmp_path / 'cpuinfo'
   cpuInfoPath.write_text(cpuInfo(), encoding='ascii')
   return AmdPcieKernelDriver(PATH=str(tmp_path), CPUINFO_PATH=str(cpuInfoPath))


def testPrerequisiteRegistration():
   assert any(isinstance(driver, AmdPcieKernelDriver)
              for driver in prerequisites.PREREQUISITES)


def testModuleSysfsPath():
   driver = AmdPcieKernelDriver()
   assert driver.MODULE == 'arista-amd-pcie'
   assert driver.getSysfsPath() == '/sys/module/arista_amd_pcie'


@pytest.mark.parametrize('family,model,profile', [
   (0x19, 0x44, 'V3000'),
   (0x17, 0x01, 'Snowy Owl'),
   (0x1a, 0x44, 'Fire Range'),
])
def testAppliesOnce(policyDriver, family, model, profile):
   with open(policyDriver.CPUINFO_PATH, 'w', encoding='ascii') as entry:
      entry.write(cpuInfo(family=family, model=model))
   with open(os.path.join(policyDriver.getSysfsPath(), 'profile'),
             'w', encoding='ascii') as entry:
      entry.write('  ' + profile + '\n')
   path = os.path.join(policyDriver.getSysfsPath(), 'apply_policy')
   with open(path, 'w', encoding='ascii') as entry:
      entry.write('0\n')
   with patch.object(KernelDriver, 'loaded', return_value=False), \
        patch('arista.core.driver.kernel.modprobe') as modprobe:
      policyDriver.setup()
      modprobe.assert_called_once_with(policyDriver.MODULE, [])
   with open(path, encoding='ascii') as entry:
      assert entry.read() == '1'
   with patch.object(KernelDriver, 'setup'), \
        patch('arista.core.utils.writeConfig') as write:
      policyDriver.setup()
      write.assert_not_called()


def assertUnsupportedCpu(policyDriver, info):
   with open(policyDriver.CPUINFO_PATH, 'w', encoding='ascii') as entry:
      entry.write(info)
   with patch.object(KernelDriver, 'setup') as setup, \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent') as read, \
        patch('arista.core.utils.writeConfig') as write, \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      policyDriver.setup()
      setup.assert_not_called()
      read.assert_not_called()
      write.assert_not_called()
      log.error.assert_not_called()
      log.exception.assert_not_called()


@pytest.mark.parametrize('info', [
   cpuInfo(vendor='GenuineIntel'),
   cpuInfo(vendor='HygonGenuine'),
   cpuInfo(family=0x18),
   cpuInfo(model=0x43),
   cpuInfo(flags='fpu\thypervisor  sse2'),
])
def testUnsupportedHardware(policyDriver, info):
   assertUnsupportedCpu(policyDriver, info)


@pytest.mark.parametrize('field', ['vendor_id', 'cpu family', 'model', 'flags'])
def testIncompleteCpuIdentity(policyDriver, field):
   info = '\n'.join(line for line in cpuInfo().splitlines()
                    if line.partition(':')[0].strip() != field)
   assertUnsupportedCpu(policyDriver, info)


@pytest.mark.parametrize('info', [
   '', '\n', 'processor: 0\ninvalid cpu data\n',
   cpuInfo(family='invalid'), cpuInfo(model='invalid'),
   cpuInfo(family='0x19'), cpuInfo(model='0x44'), cpuInfo(flags=''),
])
def testMalformedCpuInfo(policyDriver, info):
   assertUnsupportedCpu(policyDriver, info)


@pytest.mark.parametrize('firstSupported', [False, True])
def testUsesFirstCpuRecord(policyDriver, firstSupported):
   supported = cpuInfo()
   unsupported = cpuInfo(vendor='GenuineIntel')
   with open(policyDriver.CPUINFO_PATH, 'w', encoding='ascii') as entry:
      entry.write(supported + unsupported if firstSupported
                  else unsupported + supported)
   with patch.object(KernelDriver, 'setup') as setup, \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              side_effect=['V3000', '1']) as read, \
        patch('arista.core.utils.writeConfig') as write:
      policyDriver.setup()
      if firstSupported:
         setup.assert_called_once_with()
         assert read.call_count == 2
      else:
         setup.assert_not_called()
         read.assert_not_called()
      write.assert_not_called()


@pytest.mark.parametrize('error', [
   FileNotFoundError('cpuinfo missing'),
   PermissionError('cpuinfo unreadable'),
])
def testCpuInfoReadFailureCanBeRetried(policyDriver, error):
   with patch.object(KernelDriver, 'setup') as setup, \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              side_effect=['V3000', '1']) as read, \
        patch('arista.core.utils.writeConfig') as write, \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      with patch('arista.core.driver.kernel.amd_pcie.open', side_effect=error):
         policyDriver.setup()
      setup.assert_not_called()
      read.assert_not_called()
      write.assert_not_called()
      log.exception.assert_called_once()
      policyDriver.setup()
      setup.assert_called_once_with()
      assert read.call_count == 2
      write.assert_not_called()
      log.exception.assert_called_once()


@pytest.mark.parametrize('kernelProfile', [
   'Snowy Owl', 'Fire Range', 'none', 'future profile',
])
@pytest.mark.parametrize('state', ['0', '1'])
def testProfileMismatchContinuesInitialization(policyDriver, kernelProfile, state):
   path = os.path.join(policyDriver.getSysfsPath(), 'apply_policy')
   with open(path, 'w', encoding='ascii') as entry:
      entry.write(state + '\n')
   with patch.object(KernelDriver, 'setup') as setup, \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              return_value=kernelProfile + '\n') as read, \
        patch('arista.core.utils.writeConfig') as write, \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      policyDriver.setup()
      setup.assert_called_once_with()
      read.assert_called_once_with(os.path.join(policyDriver.getSysfsPath(),
                                               'profile'))
      write.assert_not_called()
      log.error.assert_called_once_with(
         'AMD PCIe policy profile mismatch: userspace=%s kernel=%s',
         'V3000', kernelProfile)
      log.exception.assert_not_called()


def testPrerequisitesContinueAfterMismatch(policyDriver):
   nextDriver = Mock()
   with patch.object(prerequisites, 'PREREQUISITES', [policyDriver, nextDriver]), \
        patch.object(KernelDriver, 'setup'), \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              return_value='none'), \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      prerequisites.loadPrerequisites()
      log.error.assert_called_once()
      nextDriver.setup.assert_called_once_with()


@pytest.mark.parametrize('profile', ['', '\n', '  \n'])
def testEmptyProfileIsReported(policyDriver, profile):
   with patch.object(KernelDriver, 'setup'), \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              return_value=profile) as read, \
        patch('arista.core.utils.writeConfig') as write, \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      policyDriver.setup()
      read.assert_called_once_with(os.path.join(policyDriver.getSysfsPath(),
                                               'profile'))
      write.assert_not_called()
      log.exception.assert_called_once()


@pytest.mark.parametrize('error', [
   FileNotFoundError('profile missing'),
   PermissionError('profile unreadable'),
])
def testProfileReadFailureContinuesInitialization(policyDriver, error):
   with patch.object(KernelDriver, 'setup'), \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              side_effect=error) as read, \
        patch('arista.core.utils.writeConfig') as write, \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      policyDriver.setup()
      read.assert_called_once_with(os.path.join(policyDriver.getSysfsPath(),
                                               'profile'))
      write.assert_not_called()
      log.exception.assert_called_once()


def testMissingPolicyStateIsReported(policyDriver):
   with patch.object(KernelDriver, 'setup'), \
        patch('arista.core.utils.writeConfig') as write, \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      policyDriver.setup()
      write.assert_not_called()
      log.exception.assert_called_once()


@pytest.mark.parametrize('architecture', ['aarch64', 'armv7l', 'i686'])
def testUnsupportedArchitecture(policyDriver, architecture):
   with patch('platform.machine', return_value=architecture), \
        patch.object(KernelDriver, 'setup') as setup, \
        patch('arista.core.driver.kernel.amd_pcie.open') as cpu, \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent') as read:
      policyDriver.setup()
      setup.assert_not_called()
      cpu.assert_not_called()
      read.assert_not_called()


def testSimulation(policyDriver):
   with patch('arista.core.utils.inSimulation', return_value=True), \
        patch.object(KernelDriver, 'setup') as setup, \
        patch('arista.core.driver.kernel.amd_pcie.open') as cpu, \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent') as read:
      policyDriver.setup()
      setup.assert_called_once_with()
      cpu.assert_not_called()
      read.assert_not_called()


@pytest.mark.parametrize('error', [
   OSError('module missing'),
   subprocess.CalledProcessError(1, ['modprobe']),
])
def testLoadFailureContinuesInitialization(policyDriver, error):
   with patch.object(KernelDriver, 'setup', side_effect=error), \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      policyDriver.setup()
      log.exception.assert_called_once()


@pytest.mark.parametrize('state', ['', 'invalid', '2'])
def testBadStateIsReported(policyDriver, state):
   with patch.object(KernelDriver, 'setup'), \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              side_effect=['V3000', state]), \
        patch('arista.core.utils.writeConfig') as write, \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      policyDriver.setup()
      write.assert_not_called()
      log.exception.assert_called_once()


def testWriteFailureCanBeRetried(policyDriver):
   with patch.object(KernelDriver, 'setup'), \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              side_effect=['V3000', '0', '0', 'V3000', '0', '1']), \
        patch('arista.core.utils.open', mock_open()) as entry, \
        patch('arista.core.utils.logging') as configLog, \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      entry.side_effect = OSError('kernel rejected the update')
      policyDriver.setup()
      configLog.error.assert_called_once()
      log.exception.assert_called_once()
      entry.side_effect = None
      policyDriver.setup()
      entry().write.assert_called_once_with('1')
      assert log.exception.call_count == 1


def testReadbackFailureIsReported(policyDriver):
   with patch.object(KernelDriver, 'setup'), \
        patch('arista.core.driver.kernel.amd_pcie.readFileContent',
              side_effect=['V3000', '0', '0']), \
        patch('arista.core.utils.writeConfig'), \
        patch('arista.core.driver.kernel.amd_pcie.logging') as log:
      policyDriver.setup()
      log.exception.assert_called_once()
