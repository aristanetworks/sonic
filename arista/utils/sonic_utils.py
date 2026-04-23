import os
import re
import subprocess
from collections import namedtuple

from .. import platforms
from ..core import platform
from ..libs.docker import runningInContainer

Port = namedtuple('Port', ['portNum', 'lanes', 'offset', 'singular', 'alias'])

def parsePortConfig():
   '''
   Returns a dictionary mapping port name ("Ethernet48") to a named tuple of port
   number, # of lanes, the offset (0 to 3 from the first lane in qsfp) and the
   singularity of the lane (if it is in 100G/40G mode)
   '''
   portMapping = {}

   portConfigPathList = getPortConfigPaths()
   for portConfigFile in portConfigPathList:
      with open(portConfigFile) as fp:
         header = fp.readline()[1:].split()
         headerMap = {key.strip(): idx for (idx, key) in enumerate(header)}
         for line in fp:
            line = line.strip()
            if not line or line[0] == '#':
               continue

            fields = line.split()
            # "portNum" is determined from the "index" column or derived from the
            # "alias" column.
            # "lanes" is determined from the number of lanes in the "lanes" column.
            # "offset" is determined from the second number of the "alias" column.
            # "singular" is determined by if the alias has a '/' character or not.
            name = fields[headerMap['name']]
            lanes = len(fields[headerMap['lanes']].split(','))
            alias = fields[headerMap['alias']]
            aliasRe = re.findall(r'\d+', alias)
            portNum = int(aliasRe[0])
            singular = True if len(aliasRe) < 2 else False
            offset = 0 if singular else (int(aliasRe[1]) - 1)

            portMapping[name] = Port(portNum, lanes, offset, singular, alias)

   return portMapping

def getSonicConfigVar(name):
   return subprocess.check_output(['sonic-cfggen', '-d', '-v',
                                   name.replace('"', "'")],
                                  text=True).strip()

def getSonicVersVar(name):
   return subprocess.check_output(['sonic-cfggen', '-y',
                                   '/etc/sonic/sonic_version.yml',
                                   '-v', name.replace('"', "'")],
                                  text=True).strip()
def getSonicPlatformName():
   platformKey = "DEVICE_METADATA['localhost']['platform']"
   return getSonicConfigVar(platformKey)

def getSonicHwSkuName():
   hwSkuKey = "DEVICE_METADATA['localhost']['hwsku']"
   return getSonicConfigVar(hwSkuKey)

def getPlatformPath():
   if runningInContainer():
      return "/usr/share/sonic/platform"
   return os.path.join("/usr/share/sonic/device/", getSonicPlatformName())

def getHwSkuPath():
   if runningInContainer():
      return "/usr/share/sonic/hwsku"
   return os.path.join(getPlatformPath(), getSonicHwSkuName())

def getPortConfigPaths():
   '''
   Create and return a list of files to read that contain the
   port configuration information. Currently that is one or more
   port_config.ini files. For the multi-asic linecard there may be
   a single file or one for each asic.
   In the future this information may be obtained from the files
   platform.json and/or hwsku.json.
   '''
   portConfigPathList = []
   hwSkuPath = getHwSkuPath()
   commonPortConfig = os.path.join(hwSkuPath, "port_config.ini")
   if os.path.exists(commonPortConfig):
      portConfigPathList.append(commonPortConfig)
   else:
      files = os.listdir(hwSkuPath)
      for fname in files:
         fpath = os.path.join(hwSkuPath, fname)
         if fname.isdigit() and os.path.isdir(fpath):
            fileName = os.path.join(hwSkuPath, fname, "port_config.ini")
            portConfigPathList.append(fileName)
   return portConfigPathList

def getPlatform():
   return platform.getPlatform()

def getInventory():
   return getPlatform().getInventory()
