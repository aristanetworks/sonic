
import os
import subprocess

from ..core.log import getLogger
from ..core.utils import inSimulation
from ..libs.fs import writeFileContent

from .nic import Nic

logging = getLogger(__name__)

class BmcUsbDeviceNic(Nic):
   """BMC side — USB gadget NIC.

   Sets up a USB-NCM network gadget via ConfigFS so the BMC is reachable from
   the host CPU over a USB eth link.
   """

   KERNEL_IFACE = 'usb0'
   WAIT_TIMEOUT = 10
   CONFIGFS_MOUNT = '/sys/kernel/config'
   GADGET_NAME = 'g1'
   FUNCTION_TYPE = 'ncm'
   VENDOR_ID = '0x1d6b'      # Linux Foundation
   PRODUCT_ID = '0x0104'     # Multifunction Composite Gadget
   SERIAL_NUMBER = '0123456789'
   MANUFACTURER = 'Arista Networks'
   PRODUCT_NAME = 'BMC USB Network Device'
   DEV_MAC = '02:00:00:00:00:01'
   HOST_MAC = '02:00:00:00:00:02'

   def __init__(self, udcName, **kwargs):
      super().__init__(**kwargs)
      self.udcName = udcName

   def setup(self):
      super().setup()

      if inSimulation():
         logging.debug('%s: simulation, skipping USB device setup', self)
         return

      if not os.path.ismount(self.CONFIGFS_MOUNT):
         raise RuntimeError('%s: ConfigFS not mounted at %s' %
                            (self, self.CONFIGFS_MOUNT))

      gadgetDir = os.path.join(self.CONFIGFS_MOUNT,
                               'usb_gadget', self.GADGET_NAME)

      self._removeExistingGadget(gadgetDir)
      self._createGadget(gadgetDir)
      self._bindUdc(gadgetDir)

      logging.info('%s: USB network gadget initialized', self)

   def clean(self):
      if inSimulation():
         logging.debug('%s: simulation, skipping USB device clean', self)
         super().clean()
         return

      gadgetDir = os.path.join(self.CONFIGFS_MOUNT,
                               'usb_gadget', self.GADGET_NAME)
      self._removeExistingGadget(gadgetDir)
      logging.info('%s: USB network gadget removed', self)

      super().clean()

   def configure(self, ifName, addr, prefixLen):
      if inSimulation():
         logging.debug('%s: simulation, skipping configure', self)
         return

      if os.path.exists('/sys/class/net/%s' % ifName):
         logging.debug('%s: %s already exists, re-assigning address', self, ifName)
         self.assignAddr(ifName, addr, prefixLen)
         return

      self.waitForInterface(self.KERNEL_IFACE)

      if ifName != self.KERNEL_IFACE:
         self.renameInterface(self.KERNEL_IFACE, ifName)

      self.assignAddr(ifName, addr, prefixLen)
      logging.info('%s: configured %s with %s/%d', self, ifName, addr, prefixLen)

   def unconfigure(self, ifName):
      if inSimulation():
         logging.debug('%s: simulation, skipping unconfigure', self)
         return

      if not os.path.exists('/sys/class/net/%s' % ifName):
         logging.debug('%s: %s not found, nothing to unconfigure', self, ifName)
         return

      subprocess.check_call(['ip', 'address', 'flush', 'dev', ifName])
      subprocess.check_call(['ip', 'link', 'set', ifName, 'down'])
      if ifName != self.KERNEL_IFACE:
         self.renameInterface(ifName, self.KERNEL_IFACE)
      logging.info('%s: unconfigured %s', self, ifName)

   # --- internal helpers --------------------------------------------------

   def _removeExistingGadget(self, gadgetDir):
      if not os.path.isdir(gadgetDir):
         return

      # Unbind UDC first
      udcPath = os.path.join(gadgetDir, 'UDC')
      if os.path.exists(udcPath):
         try:
            writeFileContent(udcPath, '')
         except IOError:
            pass

      # ConfigFS attribute files are virtual and cannot be deleted.
      # Only rmdir works — the kernel destroys the object and its attributes.
      # Symlinks must be unlinked first, and then directories removed bottom-up.
      for dirpath, dirnames, filenames in os.walk(gadgetDir, topdown=False):
         for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
               os.unlink(path)
         try:
            os.rmdir(dirpath)
         except OSError:
            pass

   def _createGadget(self, gadgetDir):
      os.makedirs(gadgetDir, exist_ok=True)

      # USB device descriptor
      writeFileContent(os.path.join(gadgetDir, 'idVendor'), self.VENDOR_ID)
      writeFileContent(os.path.join(gadgetDir, 'idProduct'), self.PRODUCT_ID)
      writeFileContent(os.path.join(gadgetDir, 'bcdDevice'), '0x0100')
      writeFileContent(os.path.join(gadgetDir, 'bcdUSB'), '0x0200')

      # English strings
      stringsDir = os.path.join(gadgetDir, 'strings', '0x409')
      os.makedirs(stringsDir, exist_ok=True)
      writeFileContent(os.path.join(stringsDir, 'serialnumber'),
                      self.SERIAL_NUMBER)
      writeFileContent(os.path.join(stringsDir, 'manufacturer'),
                      self.MANUFACTURER)
      writeFileContent(os.path.join(stringsDir, 'product'),
                      self.PRODUCT_NAME)

      # Configuration
      configStrDir = os.path.join(gadgetDir, 'configs', 'c.1',
                                  'strings', '0x409')
      os.makedirs(configStrDir, exist_ok=True)
      writeFileContent(
         os.path.join(configStrDir, 'configuration'),
         '%s Network' % self.FUNCTION_TYPE.upper())
      writeFileContent(
         os.path.join(gadgetDir, 'configs', 'c.1', 'MaxPower'), '250')

      # NCM network function
      funcName = '%s.%s' % (self.FUNCTION_TYPE, self.GADGET_NAME)
      funcDir = os.path.join(gadgetDir, 'functions', funcName)
      os.makedirs(funcDir, exist_ok=True)
      writeFileContent(os.path.join(funcDir, 'dev_addr'), self.DEV_MAC)
      writeFileContent(os.path.join(funcDir, 'host_addr'), self.HOST_MAC)

      # Link function to configuration
      linkPath = os.path.join(gadgetDir, 'configs', 'c.1', funcName)
      if not os.path.exists(linkPath):
         os.symlink(funcDir, linkPath)

      logging.debug('%s: created gadget %s with %s function',
                    self, self.GADGET_NAME, self.FUNCTION_TYPE.upper())

   def _bindUdc(self, gadgetDir):
      udcPath = '/sys/class/udc/%s' % self.udcName
      if not os.path.exists(udcPath):
         raise RuntimeError('%s: UDC %s not found' % (self, self.udcName))

      logging.debug('%s: using UDC %s', self, self.udcName)
      writeFileContent(os.path.join(gadgetDir, 'UDC'), self.udcName)
