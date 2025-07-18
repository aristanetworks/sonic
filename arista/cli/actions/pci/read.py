from . import getResourcePath
from .. import registerAction
from ...args.pci.read import readParser
from ....core.log import getLogger
from ....core.utils import MmapResource

logging = getLogger(__name__)

def readPciAddress(device: str, resource: str, address: int, size: int) -> bool:
   path = getResourcePath(device, resource)
   if not path:
      return False

   try:
      with MmapResource(path) as mmapData:
         read = getattr(mmapData, f'read{size}')
         val = read(address)
         print(f'{val:#x}')
         return True
   except Exception as e: # pylint: disable=broad-except
      logging.error('Cannot read %s device resource: %s', device, str(e))
      return False

@registerAction(readParser)
def doRead(ctx, args): # pylint: disable=unused-argument
   return readPciAddress(args.device, args.resource, args.address, args.size)
