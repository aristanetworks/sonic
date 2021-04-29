#!/usr/bin/env python3

from __future__ import print_function

import argparse
import sys

class Xcvr(object):
   def __init__(self, xcvrType, xcvrId, bus, addr):
      self.type = xcvrType.upper()
      self.id = xcvrId
      self.bus = bus
      self.addr = addr

   def __eq__(self, other):
      if not isinstance(other, self.__class__):
         return False
      return self.type == other.type and \
             self.id == other.id and \
             self.bus == other.bus and \
             self.addr == other.addr

class XcvrMap(object):
   def __init__(self, name):
      self.name = '%s_xcvrs' % name
      self.xcvrs = []

   def add(self, xcvr):
      self.xcvrs.append(xcvr)

   def toC(self):
      data = ""
      data += "static const struct xcvr_info %s[] = {\n" % self.name
      for xcvr in self.xcvrs:
         data += '   %s(.id = %s, .bus = "%s", .addr = %#x),\n' % (
               xcvr.type, xcvr.id, xcvr.bus, xcvr.addr)
      data += "};\n"
      return data

   def __eq__(self, other):
      if not isinstance(other, self.__class__):
         return False
      if len(self.xcvrs) != len(other.xcvrs):
         return False
      for s, o in zip(self.xcvrs, other.xcvrs):
         if s != o:
            return False
      return True

class Platform(object):
   def __init__(self, sid, base, xcvrMap):
      self.sid = sid
      self.xcvrMap = xcvrMap

   def toC(self):
      return '   PLATFORM("%s", %s),\n' % (self.sid, self.xcvrMap.name)

class SfpEepromGenerator(object):
   def __init__(self):
      self.xcvrMaps = {}
      self.platforms = []

   def addUniqueXcvrMap(self, xcvrMap):
      for m in self.xcvrMaps.values():
         if m == xcvrMap:
            xcvrMap = m
            break
      self.xcvrMaps[xcvrMap.name] = xcvrMap
      return xcvrMap

   def computePlatform(self, cls):
      platform = cls()
      xcvrMap = XcvrMap(platform.__class__.__name__.lower())
      base = None

      for xcvr in platform.getInventory().getXcvrs().values():
         addr = xcvr.addr
         xcvrMap.add(Xcvr(xcvr.getType(), xcvr.xcvrId, addr.busName, addr.address))

      xcvrMap = self.addUniqueXcvrMap(xcvrMap)

      for sid in platform.SID:
         self.platforms.append(Platform(sid, base, xcvrMap))

      return True

   def compute(self):
      sys.path.insert(0, '..')
      import arista.platforms

      for cls in arista.core.platform.platforms:
         if not issubclass(cls, arista.core.fixed.FixedSystem):
            continue
         self.computePlatform(cls)

   def toC(self):
      data = ""
      for xcvrMap in self.xcvrMaps.values():
         data += xcvrMap.toC()
         data += "\n"
      data += "static const struct platform_info platforms[] = {\n"
      for platform in self.platforms:
         data += platform.toC()
      data += "};\n"
      return data

def parseArgs(args):
   parser = argparse.ArgumentParser()
   parser.add_argument('output', help='Output file for the generation')
   return parser.parse_args(args)

def main(args):
   args = parseArgs(args)

   gen = SfpEepromGenerator()
   gen.compute()
   code = gen.toC()

   path = "/dev/stdout" if args.output == "-" else args.output
   with open(path, 'w') as f:
      f.write(code)

if __name__ == '__main__':
   main(sys.argv[1:])
