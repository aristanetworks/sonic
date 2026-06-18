from .driver.kernel import KernelDriver

PREREQUISITES = [
   KernelDriver(module='i2c-dev'),
]

def loadPrerequisites():
   for driver in PREREQUISITES:
      driver.setup()
