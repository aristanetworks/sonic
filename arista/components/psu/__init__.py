from ...accessors.gpio import FuncGpioImpl

from ...core.component import Priority
from ...core.component.i2c import I2cComponent

from ...drivers.pmbus import PmbusKernelDriver

class PmbusPsu(I2cComponent):
   DRIVER = PmbusKernelDriver
   PRIORITY = Priority.POWER

   def getInputOkGpio(self):
      def _isGood(value=None):
         try:
            with open(self.driver.getHwmonEntry('power1_input')) as f:
               return 1 if int(f.read()) else 0
         except Exception:
            return 0
      return FuncGpioImpl(_isGood, 'input_ok')

   def getOutputOkGpio(self, name=''):
      def _isGood(value=None):
         try:
            with open(self.driver.getHwmonEntry('power2_input')) as f:
               return 1 if int(f.read()) else 0
         except Exception:
            return 0
      return FuncGpioImpl(_isGood, 'output_ok')
