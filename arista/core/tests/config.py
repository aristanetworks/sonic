from tempfile import NamedTemporaryFile
import yaml

from ..config import Config
from ...tests.testing import unittest, patch

class ConfigTest(unittest.TestCase):
   def tearDown(self):
      self._setConfigToDefault()

   def setUp(self):
      self._setConfigToDefault()

   def testCmdlineParse(self):
      testConfig = {
         "cooling_min_speed": 0,
         "cooling_target_offset": 5,
         "etc_path":  "/etc/sonic123",
         "cooling_data_points": 1,
      }

      with patch("arista.core.config.getCmdlineDict") as mockedCmdlineDict:
         mockedCmdlineDict.return_value = {
            f"arista.{key}": value
            for key, value in testConfig.items()
         }

         Config()._parseCmdline() #pylint: disable=protected-access

         for key, value in testConfig.items():
            self._assertConfigHasAttr(key)
            self._assertAtrEqual(
               key, atrOut=getattr(Config(), key), atrExpected=value)

   @patch("arista.core.config.FLASH_CONFIG_PATH", new="")
   def testConfigParse(self):
      with NamedTemporaryFile("w") as tmpf:
         testConfig = {
            "cooling_min_speed": 0,
            "cooling_target_offset": 5,
            "etc_path":  "/etc/sonic321",
            "cooling_data_points": 5,
         }

         yaml.dump(testConfig, tmpf, sort_keys=False)
         tmpf.flush()
         with patch("arista.core.config.CONFIG_PATH", new=tmpf.name):
            Config()._parseConfig() #pylint: disable=protected-access
            for key, value in testConfig.items():
               self._assertConfigHasAttr(key)
               self._assertAtrEqual(
                  key, atrOut=getattr(Config(), key), atrExpected=value)
         tmpf.close()

   def testSetAtrTrue(self):
      testConfig = {
         "power_off_fabric_on_reboot": "y",
         "write_hw_thresholds": "yes",
         "report_hw_thresholds": "true",
      }

      for key, value in testConfig.items():
         Config().setAttr(key, value)

         self._assertConfigHasAttr(key)
         self._assertAtrEqual(key, atrOut=getattr(Config(), key), atrExpected=True)

   def testSetAtrFalse(self):
      testConfig = {
         "api_use_sfpoptoe": "n",
         "api_sfp_thermal": "no",
         "api_sfp_reset_lpmode": "False",
      }

      for key, value in testConfig.items():
         Config().setAttr(key, value)
         self._assertConfigHasAttr(key)
         self._assertAtrEqual(key, atrOut=getattr(Config(), key), atrExpected=False)

   def _assertAtrEqual(self, key, atrOut, atrExpected):
      self.assertIsInstance(atrOut, type(atrExpected),
                             msg=f"Attribute {key} has wrong type."
                              f"Expected: {type(atrExpected)}, Got: {type(atrOut)}")
      self.assertEqual(atrOut, atrExpected,
                       msg=f"Attribute {key} has wrong value."
                        f"Expected: {atrExpected!r}, Got: {atrOut!r}")

   def _setConfigToDefault(self):
      Config.instance_ = None
      Config()

   def _assertConfigHasAttr(self, key):
      self.assertTrue(hasattr(Config(), key),
                      msg=f"Attribute {key} does NOT exist in the Config object")
