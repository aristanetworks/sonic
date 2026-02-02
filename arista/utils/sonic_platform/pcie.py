
try:
   from arista.core.supervisor import Supervisor
   from arista.core.pci import PciNotReady, PciPort
   from arista.core.log import getLogger
   from arista.libs.pci import PciIds
   from sonic_platform_base.sonic_pcie.pcie_base import PcieBase
   from sonic_platform_base.sonic_pcie.pcie_common import PcieUtil
   from .platform import Platform
except ImportError as e:
   raise ImportError("%s - required module not found" % e)

logging = getLogger(__name__)

class Pcie(PcieUtil):
   def __init__(self, path):
      super().__init__(path)
      self._platform = Platform()
      self._pciRoot = None
      try:
         self._pciRoot = self._platform._platform.cpu.pciRoot
      except AttributeError:
         # NOTE: product hasn't been converted to dynamic pcie topology
         pass
      self._useConfig = not bool(self._pciRoot)
      self._pciIds = PciIds()
      self._pciIds.load()

   def iterPciPorts(self):
      assert self._pciRoot is not None
      platform = self._platform._platform
      skus = [platform]
      if isinstance(platform, Supervisor):
         chassis = platform.getChassis()
         chassis.loadAll()
         skus.extend(lc for lc in chassis.iterLinecards() if lc.isReady())
         skus.extend(fc for fc in chassis.iterFabrics() if fc.isReady())

      for sku in skus:
         for component in sku.iterComponents(filters=None, recursive=True):
            if isinstance(component, PciPort):
               yield component

   def pciidLookup(self, port):
      vendor = 0x0
      device = 0x0
      svendor = None
      sdevice = None
      name = str(port)
      try:
         if port.reachable():
            vendor = port.readSysfs('vendor', wait=False)
            device = port.readSysfs('device', wait=False)
            svendor = port.readSysfs('subsystem_vendor', wait=False)
            sdevice = port.readSysfs('subsystem_device', wait=False)
            name = self._pciIds.deviceName(vendor, device, svendor, sdevice)
         else:
            name += ' (unreachable)'
      except:
         name += ' (error)'
      return vendor, device, name

   def getPciPortInfo(self, port):
      if port.addr.upstream is None:
         # Ignore ports that don't have an upstream connected to a root
         # Mostly upstream ports connected to another cpu root complex
         return None

      if not port.available():
         # Ignore ports that are not available (e.g pci switch vs)
         return None

      vendor, device, name = self.pciidLookup(port)
      # NOTE: the data format is imposed by the expectations of the callers
      #       in this case pcied and pcieutil, it is what it is
      return {
         'name': name,
         'id': '%04x' % device,
         'bus': '%02x' % port.addr.bus,
         'dev': '%02x' % port.addr.device,
         'fn': str(port.addr.func),
      }

   def get_pcie_device(self):
      if self._useConfig:
         return super().get_pcie_device()
      data = []
      for port in self.iterPciPorts():
         try:
            info = self.getPciPortInfo(port)
            if info:
               data.append(info)
         except PciNotReady:
            logging.debug('PCIe port %s raised PciNotReady', port)
         except OSError:
            logging.debug('PCie port %s raised OSError', port)
      return data

   def get_pcie_check(self):
      if self._useConfig:
         return super().get_pcie_check()
      devices = self.get_pcie_device()
      for device in devices:
         bus = int(device['bus'], 16)
         dev = int(device['dev'], 16)
         func = int(device['fn'])
         result = self.check_pcie_sysfs(bus=bus, device=dev, func=func)
         device['result'] = "Passed" if result else "Failed"
      return devices

   def dump_conf_yaml(self):
      if self._useConfig:
         super().dump_conf_yaml()
