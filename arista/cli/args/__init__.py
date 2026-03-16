
from collections import OrderedDict

from ..parser import Parser
from ...core.dynload import importSubmodules

registeredParsers = OrderedDict()

def registerParser(name, parent=None, **kwargs):
   '''Arguments to provide to a subparser'''
   parentParser = registeredParsers.get(parent)
   if parent is None and parentParser is None:
      parentParser = Parser(None, None, None, None)
      registeredParsers[None] = parentParser

   def decorator(func):
      parser = getParser(func)
      if not parser:
         # FIXME: due to dynamic loading, parent parsers can be reloaded
         #        we therefore only add it if i
         parser = Parser(name, func, parentParser, kwargs)
         registeredParsers[func] = parser
         parentParser.addChild(parser)
      return func
   return decorator

def getParsers():
   return registeredParsers.values()

def getParser(parser):
   for p in registeredParsers.values():
      if p.parser is not None and \
         p.parser.__name__ == parser.__name__ and \
         p.parser.__module__ == parser.__module__:
         return p
   return None

def getRootParser():
   return registeredParsers[None]

# dynamically load all parsers
__all__ = importSubmodules(__package__).keys()
