import re

class ThermalPolicyConfig:
   def __init__(self, config, data):
      self.data = data or {}
      self.defaultKd = config.kd
      self.defaultKi = config.ki
      self.defaultKp = config.kp
      self.defaultLogic = config.logic.NAME
      self.defaultZone = config.defaultZone
      self.version = self.data.get('version', 0)
      self.profile = config.profile

      if self.version >= 1:
         profileData = self.data.get('profiles', {}).get(self.profile, {})
      else:
         profileData = self.data

      self._validateProfileData(profileData)

      self.fanConfig = profileData.get('fans', {})
      self.thermalConfig = profileData.get('thermals', {})
      self.zoneConfig = profileData.get('zones', {})

   def _validateProfileData(self, profileData):
      for cfg in profileData.get('thermals', {}).values():
         cfg.setdefault('kp', self.defaultKp)
         cfg.setdefault('ki', self.defaultKi)
         cfg.setdefault('kd', self.defaultKd)
         cfg.setdefault('zone', self.defaultZone)

      for cfg in profileData.get('fans', {}).values():
         cfg.setdefault('zone', self.defaultZone)

      for cfg in profileData.get('zones', {}).values():
         cfg.setdefault('logic', self.defaultLogic)

   def getThermalConfig(self, name):
      for pattern, cfg in self.thermalConfig.items():
         if re.fullmatch(pattern, name):
            return dict(cfg)
      return {
         'kp': self.defaultKp,
         'ki': self.defaultKi,
         'kd': self.defaultKd,
         'zone': self.defaultZone,
      }

   def getZoneLogicMap(self):
      #NOTE: add defaultZone/defautLogic for backward compatibility
      zones = {self.defaultZone: self.defaultLogic}
      zones.update({name: cfg['logic'] for name, cfg in
                    self.zoneConfig.items()})
      return zones

   def getFanConfig(self, name):
      for pattern, cfg in self.fanConfig.items():
         if re.fullmatch(pattern, name):
            return dict(cfg)
      #NOTE: To account for ChassisDBFan, which has no pattern match.
      return {'zone': self.defaultZone}
