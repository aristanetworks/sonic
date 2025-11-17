
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.utils import incrange

from ..components.pci import EcrcPciQuirk

from ..descs.xcvr import Osfp, QsfpDD, Sfp

from .cpu.redstart import RedstartCpu

from .quicksilver import QuicksilverBase

class QuicksilverRedstartBase(QuicksilverBase):
   SKU = []
   CPU_CLS = RedstartCpu

   def __init__(self):
      super().__init__()
      self.asic.quirks = [EcrcPciQuirk()]

@registerPlatform()
class QuicksilverRedstartP(QuicksilverRedstartBase):
   SID = [
      'Redstart8Mk2QuicksilverP',
      'Redstart8Mk2NQuicksilverP',
      'Redstart832Mk2QuicksilverP',
      'Redstart832Mk2NQuicksilverP',
   ]

   PORTS = PortLayout(
      (Osfp(i) for i in incrange(1, 64)),
      (Sfp(i) for i in incrange(65, 66)),
   )

@registerPlatform()
class QuicksilverRedstartDd(QuicksilverRedstartBase):
   SID = [
      'Redstart8Mk2QuicksilverDD',
      'Redstart8Mk2NQuicksilverDD',
      'Redstart832Mk2QuicksilverDD',
      'Redstart832Mk2NQuicksilverDD',
   ]

   PORTS = PortLayout(
      (QsfpDD(i) for i in incrange(1, 64)),
      (Sfp(i) for i in incrange(65, 66)),
   )

@registerPlatform()
class QuicksilverP512(QuicksilverRedstartP):
   SKU = ['DCS-7060X6-64PE-B']
   SID = [
      'QuicksilverP512',
      'Redstart8Mk2QuicksilverP512',
      'Redstart8Mk2NQuicksilverP512',
      'Redstart832Mk2QuicksilverP512',
      'Redstart832Mk2NQuicksilverP512',
   ]
