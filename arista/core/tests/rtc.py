
import pytest

from .helpers import (
   classname,
   getAllFixedSystems,
)

@pytest.mark.parametrize('platform', getAllFixedSystems(), ids=classname)
def testRtcInventory(platform):
   """Test that RTCs are properly registered and have correct types"""
   for rtc in platform.getInventory().getRtcs():
      name = rtc.getName()
      assert isinstance(name, str), \
         f"RTC getName() should return str, got {type(name)}"
      assert len(name) > 0, "RTC name should not be empty"
