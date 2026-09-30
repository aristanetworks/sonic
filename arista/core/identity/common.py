from typing import Optional

from ..log import getLogger
from ..prefdl import Prefdl

from ...libs.dmi import DmiEntry, DmiType

logging = getLogger(__name__)

def readSystemPrefdlViaDmi(entry: DmiEntry = DmiType.PREFDL) -> Optional[Prefdl]:
   try:
      return Prefdl.fromBase64(entry.decode().get('Prefdl'), skip=8)
   except PermissionError:
      raise
   except Exception: # pylint: disable=broad-except
      logging.exception('failed to read prefdl data from DMI')
      return None
