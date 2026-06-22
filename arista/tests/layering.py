import ast
import collections
from pathlib import Path

import pytest

from .testing import unittest

ARISTA_DIR = Path(__file__).resolve().parent.parent

LayerRule = collections.namedtuple('LayerRule',
                                   'name sources excludes forbidden allowlist')

RULES = (
   LayerRule(
      name='noUtilsImports',
      sources=None,
      excludes=('utils',),
      forbidden=('arista.utils',),
      allowlist={
         ('cli/actions/reboot.py', 'arista.utils.sonic_reboot'),
         ('core/reboot.py', 'arista.utils.rpc'),
         ('components/denali/linecard.py', 'arista.utils.rpc'),
         ('drivers/rpc.py', 'arista.utils.rpc'),
         ('daemon/jsonrpc.py', 'arista.utils.rpc'),
      },
   ),
   LayerRule(
      name='coreNoComponentsOrDrivers',
      sources=('core',),
      excludes=(),
      forbidden=('arista.components', 'arista.drivers'),
      allowlist={
         ('core/cpu.py', 'arista.components'),
         ('core/psu.py', 'arista.drivers'),
         ('core/xcvr.py', 'arista.components'),
      },
   ),
   LayerRule(
      name='platformsNoDrivers',
      sources=('platforms',),
      excludes=(),
      forbidden=('arista.drivers',),
      allowlist={
         ('platforms/cpu/sprucefish.py', 'arista.drivers'),
         ('platforms/fabric/eldridge.py', 'arista.drivers'),
      },
   ),
   LayerRule(
      name='noSonicImportsOutsideUtils',
      sources=None,
      excludes=('utils',),
      forbidden=('sonic_',),
      allowlist=set(),
   ),
)

def computePackage(filePath):
   modulePath = filePath.replace('/', '.')
   if modulePath.endswith('.py'):
      modulePath = modulePath[:-3]
   parts = modulePath.split('.')
   parts = parts[:-1]
   return '.'.join(parts)

def resolveImport(package, level, module, names):
   parts = package.split('.')
   goUp = level - 1
   if goUp >= len(parts):
      return []
   base = '.'.join(parts[:len(parts) - goUp]) if goUp > 0 else package
   if module is not None:
      return [f'{base}.{module}']
   return [f'{base}.{alias.name}' for alias in names]

def sourceSubPackage(relPath):
   parts = relPath.split('/')
   if parts and parts[0] == 'arista' and len(parts) >= 2:
      return parts[1]
   return None

def moduleMatches(module, prefix):
   if prefix.endswith('_'):
      return module.startswith(prefix)
   return module == prefix or module.startswith(prefix + '.')

def violatesRule(rule, relPath, module):
   source = sourceSubPackage(relPath)
   if rule.sources is not None and source not in rule.sources:
      return False
   if source in rule.excludes:
      return False
   return any(moduleMatches(module, prefix) for prefix in rule.forbidden)

def collectNodeImports(package, node):
   if isinstance(node, ast.ImportFrom) and node.level > 0:
      return [(resolved, node.lineno)
              for resolved in resolveImport(package, node.level,
                                            node.module, node.names)]
   if isinstance(node, ast.ImportFrom) and node.level == 0:
      if node.module == 'arista':
         return [(f'arista.{alias.name}', node.lineno)
                 for alias in node.names if alias.name != '*']
      if node.module and node.module.startswith(('arista.', 'sonic_')):
         return [(node.module, node.lineno)]
   if isinstance(node, ast.Import):
      return [(alias.name, node.lineno) for alias in node.names
              if alias.name == 'arista' or alias.name.startswith(
                    ('arista.', 'sonic_'))]
   return []

def collectImports(aristaDir):
   repoRoot = aristaDir.parent
   results = {}
   for fullPath in aristaDir.rglob('*.py'):
      if any(part in ('__pycache__', 'tests')
             for part in fullPath.relative_to(aristaDir).parts):
         continue
      relPath = fullPath.relative_to(repoRoot).as_posix()

      with fullPath.open() as fh:
         source = fh.read()
      try:
         tree = ast.parse(source, filename=str(fullPath))
      except SyntaxError:
         continue

      package = computePackage(relPath)
      imports = []

      for node in ast.walk(tree):
         imports.extend(collectNodeImports(package, node))

      if imports:
         results[relPath] = imports
   return results

class ImportLayeringTest(unittest.TestCase):

   importMap = None

   @classmethod
   def setUpClass(cls):
      cls.importMap = collectImports(ARISTA_DIR)

   def _checkRule(self, rule):
      violations = []
      matchedKnown = set()

      for relPath, imports in self.importMap.items():
         shortPath = relPath[len('arista/'):]
         for resolved, lineno in imports:
            if not violatesRule(rule, relPath, resolved):
               continue
            matched = False
            for knownPath, knownPrefix in rule.allowlist:
               if shortPath == knownPath and moduleMatches(resolved, knownPrefix):
                  matchedKnown.add((knownPath, knownPrefix))
                  matched = True
                  break
            if not matched:
               violations.append(f'{relPath}:{lineno}: {resolved}')

      stale = rule.allowlist - matchedKnown
      for shortPath, prefix in sorted(stale):
         violations.append(
            f'stale allowlist entry: ({shortPath!r}, {prefix!r})')

      self.assertEqual(violations, [],
                       f'import layering violations for rule {rule.name!r}')

   @pytest.mark.design
   def testImportLayering(self):
      for rule in RULES:
         with self.subTest(rule=rule.name):
            self._checkRule(rule)
