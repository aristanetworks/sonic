"""Configured local transport and unchanged chassis connector arguments."""

import sys
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from ..thermal_helper import DBHelper


@pytest.mark.parametrize('port', [0, 6379, 6400])
@pytest.mark.parametrize('name', ['STATE_DB', 'CHASSIS_STATE_DB'])
@pytest.mark.parametrize('namespace', ['', 'asic0'])
@pytest.mark.parametrize('global_initialized', [False, True])
def test_transport_arguments(port, name, namespace, global_initialized):
   native = ModuleType('swsscommon.swsscommon')
   native.DBConnector = Mock()
   native.SonicDBConfig = Mock()
   native.SonicDBConfig.getDbPort.return_value = port
   native.SonicDBConfig.isGlobalInit.return_value = global_initialized
   with patch.dict(sys.modules, {'swsscommon.swsscommon': native}):
      helper = DBHelper(namespace)
      first = helper._get_db(name)
      assert helper._get_db(name) is first
   native.DBConnector.assert_called_once_with(
      name, 0, name != 'STATE_DB' or port != 0, namespace)
   if name == 'STATE_DB':
      native.SonicDBConfig.getDbPort.assert_called_once_with(name, namespace)
   else:
      native.SonicDBConfig.getDbPort.assert_not_called()
   if namespace and not global_initialized:
      native.SonicDBConfig.load_sonic_global_db_config.assert_called_once_with()
   else:
      native.SonicDBConfig.load_sonic_global_db_config.assert_not_called()


def test_invalid_local_metadata_does_not_fall_back():
   native = ModuleType('swsscommon.swsscommon')
   native.DBConnector = Mock()
   native.SonicDBConfig = Mock()
   native.SonicDBConfig.getDbPort.side_effect = RuntimeError('missing STATE_DB')
   with patch.dict(sys.modules, {'swsscommon.swsscommon': native}):
      with pytest.raises(RuntimeError, match='missing STATE_DB'):
         DBHelper()._get_db('STATE_DB')
   native.DBConnector.assert_not_called()
