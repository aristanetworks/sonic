
import importlib
import pkgutil
import sys

if sys.version_info < (3, 12):
   get_module_loader = lambda finder, name: finder.find_module(name)
else:
   get_module_loader = lambda finder, name: finder.find_spec(name).loader

def walk_packages(path=None, prefix='', onerror=None):
   """Implementation from https://github.com/python/cpython/pull/11956"""
   def seen(p, m={}): # pylint: disable=dangerous-default-value
      if p in m:
         return True
      m[p] = True
      return False

   for info in pkgutil.iter_modules(path, prefix):
      yield info

      if info.ispkg:
         loader = get_module_loader(info.module_finder, info.name)
         try:
            # patch: don't reload imported modules
            module = sys.modules.get(info.name) or loader.load_module(info.name)
         except ImportError:
            if onerror is not None:
               onerror(info.name)
         except Exception: # pylint: disable=broad-except
            if onerror is not None:
               onerror(info.name)
            else:
               raise
         else:
            path = module.__path__

            # don't traverse path items we've seen before
            path = [p for p in path if not seen(p)]

            yield from walk_packages(path, info.name + '.', onerror)

def importSubmodules(package):
   if isinstance(package, str):
      prefix = package + '.'
      package = importlib.import_module(package)
   else:
      prefix = package.__module__

   modules = {}
   for info in walk_packages(package.__path__, prefix=prefix):
      fullName = info.name
      modules[fullName] = importlib.import_module(fullName)

   return modules
