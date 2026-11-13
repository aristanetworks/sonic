from ..core.daemon import registerDaemonFeature, OneShotFeature
from ..utils.config.platform_components_updater import PlatformComponentsUpdater
from ..utils.config.platform_config_updater import PlatformConfigUpdater

@registerDaemonFeature()
class PlatformConfigUpdateFeature(OneShotFeature):

   NAME = 'platform-config-update'

   def run(self):
      PlatformConfigUpdater(self.daemon.platform).update()
      PlatformComponentsUpdater(self.daemon.platform).update()
