
from ...core.platform import registerPlatform

from ...components.denali.chassis import DenaliChassis

@registerPlatform()
class NorthFace(DenaliChassis):
   SID = []
   SKU = ['DCS-7808-CH']

   NUM_LINECARDS = 8
   NUM_FABRICS = 6
   NUM_FANS = 48
   NUM_PSUS = 12
   MIN_REQUIRED_PSUS = 6
