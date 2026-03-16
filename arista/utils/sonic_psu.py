from .sonic_utils import getInventory

from .. import platforms # pylint: disable=unused-import
from ..core import platform
from ..core.supervisor import Supervisor

try:
   from sonic_psu.psu_base import PsuBase
except ImportError as e:
   raise ImportError("%s - required module not found" % str(e))

def getPsuUtil():
   inventory = getInventory()

   class PsuUtil(PsuBase):
      """Platform-specific PsuUtil class"""

      def _get_psu(self, index):
         if inventory.getNumPsuSlots():
            if 0 <= index < inventory.getNumPsuSlots():
               return inventory.getPsuSlot(index)
         else:
            if 0 <= index < inventory.getNumPsus():
               return inventory.getPsu(index)
         return None

      def get_psu_presence(self, index):
         psu = self._get_psu(index - 1)
         return psu.getPresence() if psu else False

      def get_psu_status(self, index):
         psu = self._get_psu(index - 1)
         return psu.getStatus() if psu else False

      def get_num_psus(self):
         if isinstance(platform.getPlatform(), Supervisor):
            return platform.getPlatform().getChassis().NUM_PSUS
         return inventory.getNumPsuSlots() or inventory.getNumPsus()

   return PsuUtil
