import gzip
import os
import shutil
import tempfile
from contextlib import contextmanager

def atomicWrite(path, content, mode=0o644):
   outDir = os.path.dirname(path)
   with tempfile.NamedTemporaryFile('w', dir=outDir, delete=False, suffix='.tmp') \
         as tmp:
      try:
         tmp.write(content)
         os.fsync(tmp.fileno())
         os.chmod(tmp.name, mode)
         os.replace(tmp.name, path)
      except BaseException:
         os.unlink(tmp.name)
         raise

def readFileContent(path):
   with open(path) as f:
      return f.read()

def writeFileContent(path, value, encoding='utf-8'):
   with open(path, 'w', encoding=encoding) as f:
      f.write(value)

def touch(path, mode=0o644, times=None):
   try:
      with open(path, 'a'):
         pass
      os.chmod(path, mode)
      os.utime(path, times)
   except IOError:
      return False
   return True

def rmfile(path, raises=False):
   try:
      os.remove(path)
   except (OSError, IOError):
      if raises:
         raise

class RotatedLogFile:
   def __init__(self, name, path, keep, compress):
      self.name = name
      self.path = path
      self.keep = keep
      self.compress = compress

   def _rotate(self):
      logs = sorted(f for f in os.listdir(self.path) if f.startswith(self.name))
      while len(logs) >= self.keep:
         os.remove(os.path.join(self.path, logs.pop(0)))

   @contextmanager
   def newLog(self, suffix):
      os.makedirs(self.path, exist_ok=True)
      self._rotate()
      path = os.path.join(self.path, f'{self.name}.{suffix}.log')
      with open(path, 'wb') as f:
         yield f
      if self.compress:
         zipPath = os.path.join(self.path, f'{self.name}.{suffix}.log.gz')
         with open(path, 'rb') as rawFile, gzip.open(zipPath, 'wb') as zipFile:
            shutil.copyfileobj(rawFile, zipFile)
         rmfile(path)
