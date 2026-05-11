from unittest.mock import patch

import pytest

from ...core import utils
from ...core.tests.helpers import getAllFixedSystemKeys

from .. import cleanupSimulation, main, setupSimulation

def fakesleep(_):
   pass

PLATFORM_KEYS = list(getAllFixedSystemKeys())
SUP_KEYS = (frozenset(PLATFORM_KEYS) -
            frozenset(getAllFixedSystemKeys(ignoreSupervisor=True)))

_INITIAL_SIMULATION = utils.simulation

class SimulationBase:
   def setup_method(self):
      setupSimulation()

   def teardown_method(self):
      cleanupSimulation()
      utils.simulation = _INITIAL_SIMULATION

def _runMain(args, code=0):
   exitCode = main(args)
   assert exitCode == code, f'Command {args} failed with code {exitCode}'

@patch('time.sleep', fakesleep)
class TestCliBasic(SimulationBase):
   def testSysEeprom(self):
      _runMain(['syseeprom'])

   def testPlatforms(self):
      _runMain(['platforms'])

   def testHelpAll(self):
      with pytest.raises(SystemExit) as exc:
         _runMain(['--help-all'])
      assert exc.value.code == 0

   def testDiagIo(self):
      # TODO: fix simulation mode
      #_runMain(['-p', key, 'platform', 'diag'])
      pytest.skip('simulation mode not yet supported')

@pytest.mark.parametrize('key', PLATFORM_KEYS)
@patch('time.sleep', fakesleep)
class TestCliPerPlatform(SimulationBase):
   def testSetup(self, key):
      _runMain(['-p', key, 'setup'])

   def testResetToggle(self, key):
      _runMain(['-p', key, 'reset', '--toggle'])

   def testClean(self, key):
      _runMain(['-p', key, 'clean'])

   def testDump(self, key):
      if key in SUP_KEYS:
         pytest.skip('dump not supported on supervisors')
      _runMain(['-p', key, 'dump'])

   def testRebootCause(self, key):
      _runMain(['-p', key, 'reboot-cause'])

   def testDiag(self, key):
      _runMain(['-p', key, 'platform', 'diag', '--noIo'])

   def testWatchdogStatus(self, key):
      _runMain(['-p', key, 'watchdog', '--status'])

   def testWatchdogArm(self, key):
      _runMain(['-p', key, 'watchdog', '--arm'])

   def testWatchdogArmTimeout(self, key):
      _runMain(['-p', key, 'watchdog', '--arm', '250'])

   def testWatchdogStop(self, key):
      _runMain(['-p', key, 'watchdog', '--stop'])
