
from collections import OrderedDict

from ..parser import Parser
from ...core.dynload import importSubmodules

registeredParsers = OrderedDict()

def _parser_key(parser_func):
   # For sanity, make it resiliant to module reload
   # (i.e. use the func identifier, not the func itself)
   if parser_func:
      return (parser_func.__module__, parser_func.__name__)
   return None

_duplicates = set()  # for inspection in tests

def registerParser(name, parent=None, **kwargs):
   '''Arguments to provide to a subparser'''
   parentParser = getParser(parent)
   if parent is None and parentParser is None:
      parentParser = Parser(None, None, None, None)
      registeredParsers[_parser_key(None)] = parentParser

   def decorator(func):
      key = _parser_key(func)
      if key not in registeredParsers:
         parser = Parser(name, func, parentParser, kwargs)
         registeredParsers[key] = parser
         parentParser.addChild(parser)
      else:
         # With proper (idempotent) module loading we should never be here
         _duplicates.add(key)
      return func
   return decorator

def getParsers():
   return registeredParsers.values()

def getParser(parser):
   return registeredParsers.get(_parser_key(parser))

def getRootParser():
   return registeredParsers[None]

# dynamically load all parsers
__all__ = importSubmodules(__package__).keys()
