import gzip
import os

from ...core.config import flashPath
from ...core.diag import DiagContext

from . import Renderer, List, Row

class ShowBlackBox(Renderer):

   NAME = 'blackbox'

   def getData(self, show):
      # Only one blackbox per platform is supported.
      ctx = DiagContext()
      bbs = [bb for platform in show.platforms
                for bb in platform.getInventory().getBlackBox()]
      decoder = bbs[0].decoder() if bbs else None

      args = show.args
      logs = []
      if args.path:
         logs.append(self._getLogData(args.path, decoder))
      else:
         for path in self._getLogFiles(all_=args.blackbox_show_all):
            logs.append(self._getLogData(path, decoder))

      return {'blackboxes': [bb.__diag__(ctx) for bb in bbs], 'logs': logs}

   def _getLogFiles(self, all_=False):
      logDir = flashPath('blackbox')
      if not os.path.exists(logDir):
         return []
      logs = sorted([os.path.join(logDir, f) for f in os.listdir(logDir)
                     if f.startswith('blackbox')])
      return logs if all_ else logs[-1:]

   def _getLogData(self, path, decoder):
      if not os.path.exists(path):
         return {'path': path,
                 'content': None,
                 'error': 'does not exist'}
      with gzip.open(path, 'rb') as f:
         data = f.read()
      content = decoder.decode(data) if decoder else None
      return {'path': path, 'content': content}

   def renderText(self, show):
      model = self.data(show)
      args = show.args
      if not args.path:
         List("BlackBox:", header=("%s", 'component'), tree=[
            Row('Enabled: %r', 'enabled'),
            Row('Version: %d', 'version'),
         ]).render(model['blackboxes'])
      for log in model['logs']:
         print(f'\n=== {os.path.basename(log["path"])} ===')
         if 'error' in log:
            print(f'Console log {log["path"]} {log["error"]}')
         elif log.get('content') is not None:
            print(log['content'])
