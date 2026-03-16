
import argparse
import importlib

from .exception import ActionError
from ..core.log import getLogger

logging = getLogger(__name__)

class CliContext():
   pass

class Parser():
   def __init__(self, name, parser, parent, kwargs, childs=None):
      self.name = name
      self.parser = parser
      self.parent = parent
      self.kwargs = kwargs
      self.childs = childs or []
      self.action = None
      self.dest = None

   def isRootNode(self):
      return self.parent is None

   def isLeaf(self):
      return not self.childs

   def isProxy(self):
      return self.name is None

   def isTargetedBy(self, args):
      return self.dest is not None and \
            getattr(args, self.dest, None) == self.name

   def __str__(self):
      if self.isRootNode():
         return 'RootParser()'
      return 'Parser(name=%s, parent=%s)' % (self.name, self.parent)

   def addChild(self, child):
      self.childs.append(child)

   def addAction(self, action):
      self.action = action

   def _runAction(self, action, ctx, args, *others, **kwargs):
      logging.debug('Running action %s', action.func.__name__)
      ret = action.func(ctx, args, *others, **kwargs)
      if ret is None or ret is True or ret == 0:
         return 0
      raise ActionError('action %s failed', code=ret)

   def runAction(self, ctx, args, *others, **kwargs):
      if not self.isLeaf():
         assert self.childs

      if not self.isProxy() and not self.isTargetedBy(args):
         return

      if self.loadAction():
         self._runAction(self.action, ctx, args, *others, **kwargs)
      else:
         logging.debug('No action available for %s', self)

      for child in self.childs:
         if child.isProxy(): # necessary for legacy command support
            found = False
            for subchild in child.childs:
               if subchild.isTargetedBy(args):
                  found = True
                  break
            if not found:
               continue
         child.runAction(ctx, args, *others, **kwargs)

   def loadAction(self):
      if not self.parser:
         return False
      module = self.parser.__module__
      actionModule = module.replace('.args.', '.actions.')
      logging.debug('Loading action module %s', actionModule)
      importlib.import_module(actionModule, package='arista')
      return bool(self.action)

   def loadActions(self):
      if self.parent:
         self.loadAction()
      for child in self.childs:
         child.loadActions()

   def applyParser(self, parser):
      if self.parser:
         self.parser(parser)

   def addChildParser(self, child, subparsers, dest, common):
      sub = subparsers.add_parser(
         child.name,
         formatter_class=argparse.RawDescriptionHelpFormatter,
         **child.kwargs
      )
      if common:
         common(sub)
      child.addSubparsers(sub, dest=dest, common=common)

   def addSubparsers(self, parser, dest='action', common=None):
      self.applyParser(parser)
      self.dest = dest

      if not self.childs:
         return

      childDest = dest if self.isProxy() else '%s_%s' % (dest, self.name)
      subparsers = parser.add_subparsers(dest=childDest)
      subparsers.add_parser('help', help='print a help message')
      for child in self.childs:
         if child.isProxy():
            assert not child.isLeaf()
            for subchild in child.childs:
               subchild.addChildParser(subchild, subparsers, childDest, common)
         else:
            self.addChildParser(child, subparsers, childDest, common)
