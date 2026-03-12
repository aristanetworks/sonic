
from ...core.platform import registerPlatform

from ...components.denali.chassis import DenaliChassis

@registerPlatform()
class Camp(DenaliChassis):
   SID = []
   SKU = ['DCS-7804-CH']

   NUM_LINECARDS = 4
   NUM_FABRICS = 6
   NUM_FANS = 24
   NUM_PSUS = 8
   MIN_REQUIRED_PSUS = 4
