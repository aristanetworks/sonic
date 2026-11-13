import os

from ...libs.nos import getPlatformPath

class ConfigUpdater:

   FILENAME = None

   def __init__(self, platform):
      self.platform = platform
      self.configPath = os.path.join(getPlatformPath(), self.FILENAME)

   def update(self):
      raise NotImplementedError
