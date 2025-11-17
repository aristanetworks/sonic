from tempfile import NamedTemporaryFile
from types import UnionType
import yaml

from ..config import Config, DefaultConfig
from ...tests.testing import unittest, patch

class MockDefaultConfig:
   testStr: str = "test"
   strOrNone: str | None = None
   testInt: int = 15
   intOrNone: int | None = None
   testFloat: float = 1.5
   floatOrNone: float | None = None
   testBool: bool = False
   boolOrNone: bool | None = None

defaultTestConfig = {
   "testStr":  "/etc/sonic123",
   "strOrNone":  "10.0.0.1",
   "testInt": 0,
   "intOrNone": 15,
   "testFloat": 1.4,
   "floatOrNone": -0.5,
   "testBool": False,
   "boolOrNone": False,
}

@patch("arista.core.config.DefaultConfig", new=MockDefaultConfig)
class ConfigTest(unittest.TestCase):
   def tearDown(self):
      self._setConfigToDefault()

   def setUp(self):
      self._setConfigToDefault()

   def testCmdlineParse(self):
      testConfig = defaultTestConfig

      with patch("arista.core.config.getCmdlineDict") as mockedCmdlineDict:
         mockedCmdlineDict.return_value = {
            f"arista.{key}": f"{value}"
            for key, value in testConfig.items()
         }

         Config()._parseCmdline() #pylint: disable=protected-access

         for key, value in testConfig.items():
            with self.subTest(msg=key):
               self._assertConfigHasAttr(key)
               self._assertAtrEqual(
                  key, atrOut=getattr(Config(), key), atrExpected=value)

   @patch("arista.core.config.FLASH_CONFIG_PATH", new="")
   def testConfigParse(self):
      with NamedTemporaryFile("w") as tmpf:
         testConfig = defaultTestConfig
         yaml.dump(testConfig, tmpf, sort_keys=False)
         tmpf.flush()

         with patch("arista.core.config.CONFIG_PATH", new=tmpf.name):
            Config()._parseConfig() #pylint: disable=protected-access

            for key, value in testConfig.items():
               with self.subTest(msg=key):
                  self._assertConfigHasAttr(key)
                  self._assertAtrEqual(
                     key, atrOut=getattr(Config(), key), atrExpected=value)

   def testSetAtrTrue(self):
      testConfig = {
         "testStr": "y",
         "testBool": "yes",
         "boolOrNone": "True",
      }

      for key, value in testConfig.items():
         with self.subTest(msg=key):
            Config().setAttr(key, value)
            self._assertConfigHasAttr(key)
            expected = True
            if key == "testStr":
               expected = value
            self._assertAtrEqual(key, atrOut=getattr(Config(), key),
                                 atrExpected=expected)

   def testSetAtrFalse(self):
      testConfig = {
         "testStr": "n",
         "testBool": "no",
         "boolOrNone": "false",
      }

      for key, value in testConfig.items():
         with self.subTest(msg=key):
            Config().setAttr(key, value)
            self._assertConfigHasAttr(key)
            expected = False
            if key == "testStr":
               expected = value
            self._assertAtrEqual(key, atrOut=getattr(Config(), key),
                                 atrExpected=expected)

   def testTypeConversion(self):
      testConfig = defaultTestConfig

      for key, value in testConfig.items():
         with self.subTest(msg=key):
            Config().setAttr(key, value)
            self._assertConfigHasAttr(key)
            type_ = type(value)
            self._assertAtrEqual(
               key, atrOut=getattr(Config(), key), atrExpected=type_(value))

   @patch('arista.core.config.logging.warning')
   def testIvalidBools(self, mock_log):
      testConfig = {
         "testBool": "invalidBool",
         "boolOrNone": 321
      }

      for key, value in testConfig.items():
         with self.subTest(msg=key):
            Config().setAttr(key, value)
            mock_log.assert_called_once()
            mock_log.reset_mock()

   def testAddAbsentAttr(self):
      testConfig = {
         "absentStr": "123",
         "absentInt": 12,
         "absentFloat": 1.5,
         "absentBool": False,
      }

      for key, value in testConfig.items():
         with self.subTest(msg=key):
            Config().setAttr(key, value)
            self._assertNoConfigAttr(key)

   def _assertAtrEqual(self, key, atrOut, atrExpected):
      self.assertIsInstance(atrOut, type(atrExpected),
                             msg=f"Attribute {key} has wrong type."
                              f"Expected: {type(atrExpected)}, Got: {type(atrOut)}")
      self.assertEqual(atrOut, atrExpected,
                       msg=f"Attribute {key} has wrong value."
                        f"Expected: {atrExpected!r}, Got: {atrOut!r}")

   def _setConfigToDefault(self):
      Config.instance_ = None

   def _assertConfigHasAttr(self, key):
      self.assertTrue(hasattr(Config(), key),
                      msg=f"Attribute {key} does NOT exist in the Config object")

   def _assertNoConfigAttr(self, key):
      self.assertFalse(hasattr(Config(), key),
                      msg=f"Attribute {key} exists in the Config object")

class DefaultConfigTest(unittest.TestCase):
   def testSingleAnnotations(self):
      for key, value in DefaultConfig.__annotations__.items():
         with self.subTest(msg=key):
            if isinstance(value, UnionType):
               types = [k for k in value.__args__ if k is not type(None)]
               self.assertEqual(len(types), 1,
                                 msg=f"DefaultConfig attribute {key} has too "
                                 f"many types besides None {len(types)} > 1")

   def testHasAnnotations(self):
      for key in DefaultConfig.__dict__:
         if key.startswith("__"):
            continue

         with self.subTest(msg=key):
            self.assertTrue(key in DefaultConfig.__annotations__,
                            msg=f"Attribute {key} does NOT have type annotation")

   def testCorrectValueType(self):
      for key, value in DefaultConfig.__dict__.items():
         if key.startswith("__"):
            continue

         with self.subTest(msg=key):
            type_ = DefaultConfig.__annotations__.get(key)
            if isinstance(type_, UnionType):
               self.assertTrue(type(value) in type_.__args__,
                               msg=f"Attribute {key} has value with unexpected type."
                               f" Expected: {type_!r}, Got: {type(value)!r}")
            else:
               self.assertTrue(type_ is type(value),
                               msg=f"Attribute {key} has value with unexpected type."
                               f" Expected: {type_!r}, Got: {type(value)!r}")
