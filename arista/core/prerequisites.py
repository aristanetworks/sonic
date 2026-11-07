from .driver.kernel import KernelDriver
from .driver.kernel.amd_pcie import AmdPcieKernelDriver

PREREQUISITES = [
   AmdPcieKernelDriver(),
   KernelDriver(module='i2c-dev'),
]

def loadPrerequisites():
   for driver in PREREQUISITES:
      driver.setup()
