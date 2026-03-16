
from ..args import getParser

class Action(object):
   def __init__(self, func, parent, kwargs):
      self.func = func
      self.parent = parent
      self.kwargs = kwargs

def registerAction(parser, **kwargs):
   '''Register an action function for a subparser'''
   parser = getParser(parser)
   def decorator(func):
      action = Action(func, parser, kwargs)
      parser.addAction(action)
      return func
   return decorator
