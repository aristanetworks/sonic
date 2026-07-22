# Copyright (c) 2026 Arista Networks, Inc.  All rights reserved.

import subprocess
from unittest.mock import Mock

import pytest

from .. import bmc_mgmt_nic
from ..bmc_mgmt_nic import BmcMgmtNic, addMacOffset, isValidMac
from ...core.inventory import Inventory


class MockEeprom:
   def __init__(self, mac='b8:a1:b8:a7:79:56'):
      self.mac = mac

   def prefdl(self):
      if isinstance(self.mac, Exception):
         raise self.mac
      return {'MAC': self.mac}


def makeNic(mac='b8:a1:b8:a7:79:56'):
   return BmcMgmtNic(cpuEeprom=MockEeprom(mac), inventory=Inventory())


@pytest.mark.parametrize(('baseMac', 'offset', 'expected'), [
   ('00:00:00:00:00:00', 2, '00:00:00:00:00:02'),
   ('00:00:00:00:00:ff', 1, '00:00:00:00:01:00'),
   ('b8:a1:b8:a7:79:56', 2, 'b8:a1:b8:a7:79:58'),
   ('FF:FF:FF:FF:FF:FD', 2, 'ff:ff:ff:ff:ff:ff'),
   ('ff:ff:ff:ff:ff:ff', 1, '00:00:00:00:00:00'),
])
def testAddMacOffset(baseMac, offset, expected):
   assert addMacOffset(baseMac, offset) == expected


@pytest.mark.parametrize(('baseMac', 'offset'), [
   ('bad', 1),
   ('00:00:00:00:00:0g', 1),
])
def testAddMacOffsetInvalid(baseMac, offset):
   with pytest.raises(ValueError):
      addMacOffset(baseMac, offset)


@pytest.mark.parametrize('mac', [
   'b8:a1:b8:a7:79:58',
   '02:00:00:00:00:01',
   '00:00:00:00:00:00',
   'ff:ff:ff:ff:ff:ff',
   '01:00:5e:00:00:01',
])
def testValidMac(mac):
   assert isValidMac(mac)


@pytest.mark.parametrize('mac', [
   None,
   'bad',
   '00:00:00:00:00:0g',
])
def testInvalidMac(mac):
   assert not isValidMac(mac)


def testReadEepromMgmtMacUsesOffset():
   nic = makeNic()

   assert nic.readEepromMgmtMac() == 'b8:a1:b8:a7:79:59'


def testReadEepromMgmtMacRejectsInvalidBaseMac():
   nic = makeNic(mac='bad')

   assert nic.readEepromMgmtMac() is None


def testConfigureEepromWinsOverStaleUboot(monkeypatch):
   nic = makeNic()
   commands = []
   setMACAddress = Mock()

   monkeypatch.setattr(bmc_mgmt_nic, 'inSimulation', lambda: False)
   monkeypatch.setattr(
      subprocess, 'check_output',
      lambda *args, **kwargs: 'b8:a1:b8:a7:79:57\n')
   monkeypatch.setattr(subprocess, 'check_call',
                       commands.append)
   monkeypatch.setattr(nic, 'waitForInterface', Mock())
   monkeypatch.setattr(nic, 'getConfiguredMac',
                       Mock(return_value='00:00:00:00:00:02'))
   monkeypatch.setattr(nic, 'setMACAddress', setMACAddress)

   nic.configure('eth0')

   assert commands == [
      ['fw_setenv', 'ethaddr', 'b8:a1:b8:a7:79:59'],
   ]
   setMACAddress.assert_called_once_with('eth0', 'b8:a1:b8:a7:79:59')

def testConfigureContinuesWhenUbootUpdateFails(monkeypatch):
   nic = makeNic()
   setMACAddress = Mock()

   monkeypatch.setattr(bmc_mgmt_nic, 'inSimulation', lambda: False)
   monkeypatch.setattr(
      subprocess, 'check_output',
      Mock(side_effect=subprocess.CalledProcessError(1, 'fw_printenv')))
   monkeypatch.setattr(
      subprocess, 'check_call',
      Mock(side_effect=subprocess.CalledProcessError(1, 'fw_setenv')))
   monkeypatch.setattr(nic, 'waitForInterface', Mock())
   monkeypatch.setattr(nic, 'getConfiguredMac',
                       Mock(return_value='00:00:00:00:00:02'))
   monkeypatch.setattr(nic, 'setMACAddress', setMACAddress)

   nic.configure('eth0')

   setMACAddress.assert_called_once_with('eth0', 'b8:a1:b8:a7:79:59')


def testConfigureFallsBackToUbootWhenEepromUnavailable(monkeypatch):
   nic = makeNic(mac=OSError('EEPROM not ready'))
   setMACAddress = Mock()

   monkeypatch.setattr(bmc_mgmt_nic, 'inSimulation', lambda: False)
   monkeypatch.setattr(
      subprocess, 'check_output',
      lambda *args, **kwargs: 'b8:a1:b8:a7:79:58\n')
   monkeypatch.setattr(nic, 'waitForInterface', Mock())
   monkeypatch.setattr(nic, 'getConfiguredMac',
                       Mock(return_value='00:00:00:00:00:02'))
   monkeypatch.setattr(nic, 'setMACAddress', setMACAddress)

   nic.configure('eth0')

   setMACAddress.assert_called_once_with('eth0', 'b8:a1:b8:a7:79:58')


def testConfigureFailsWhenNoValidMacExists(monkeypatch):
   nic = makeNic(mac=None)

   monkeypatch.setattr(bmc_mgmt_nic, 'inSimulation', lambda: False)
   monkeypatch.setattr(
      subprocess, 'check_output',
      Mock(side_effect=subprocess.CalledProcessError(1, 'fw_printenv')))

   with pytest.raises(RuntimeError):
      nic.configure('eth0')


def testConfigureSkipsWhenMacAlreadyCorrect(monkeypatch):
   nic = makeNic()
   setMACAddress = Mock()
   checkCall = Mock()

   monkeypatch.setattr(bmc_mgmt_nic, 'inSimulation', lambda: False)
   monkeypatch.setattr(
      subprocess, 'check_output',
      lambda *args, **kwargs: 'b8:a1:b8:a7:79:59\n')
   monkeypatch.setattr(subprocess, 'check_call', checkCall)
   monkeypatch.setattr(nic, 'waitForInterface', Mock())
   monkeypatch.setattr(nic, 'getConfiguredMac',
                       Mock(return_value='B8:A1:B8:A7:79:59'))
   monkeypatch.setattr(nic, 'setMACAddress', setMACAddress)

   nic.configure('eth0')

   nic.waitForInterface.assert_called_once_with('eth0')
   checkCall.assert_not_called()
   setMACAddress.assert_not_called()


def testSetMACAddressLeavesDownInterfaceDown(monkeypatch):
   nic = makeNic()
   commands = []

   monkeypatch.setattr(nic, 'isAdminUp', lambda _: False)
   monkeypatch.setattr(subprocess, 'check_call',
                       commands.append)

   nic.setMACAddress('eth0', 'b8:a1:b8:a7:79:58')

   assert commands == [
      ['ip', 'link', 'set', 'dev', 'eth0', 'address', 'b8:a1:b8:a7:79:58'],
   ]


def testSetMACAddressRestoresUpInterface(monkeypatch):
   nic = makeNic()
   commands = []

   monkeypatch.setattr(nic, 'isAdminUp', lambda _: True)
   monkeypatch.setattr(subprocess, 'check_call',
                       commands.append)

   nic.setMACAddress('eth0', 'b8:a1:b8:a7:79:58')

   assert commands == [
      ['ip', 'link', 'set', 'dev', 'eth0', 'down'],
      ['ip', 'link', 'set', 'dev', 'eth0', 'address', 'b8:a1:b8:a7:79:58'],
      ['ip', 'link', 'set', 'dev', 'eth0', 'up'],
   ]
