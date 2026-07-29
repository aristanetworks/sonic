
from __future__ import print_function

from ...core.cause import getReloadCauseManager, getLinecardReloadCauseManager

from . import Renderer

# This is a partially implemented abstract class, which pylint doesn't handle
# correctly.
# pylint: disable=abstract-method
class ShowRebootCause(Renderer):

   NAME = 'reboot-cause'

   def _getData(self, show, rcm):
      if show.args.history:
         return [rp.toDict() for rp in rcm.allReports()]
      else:
         rp = rcm.lastReport()
         return [rp.toDict()] if rp else []

   def _renderCauseText(self, cause, prefix=''):
      if cause['time'] != 'unknown':
         prefix = f"{prefix}{cause['time']} "
      print(f"{prefix}{cause['cause']} ({cause['description']})")
      if cause.get('debugInfo'):
         indent = ' ' * len(prefix) if prefix else '   '
         print(f"{indent}debugInfo: {cause['debugInfo']}")

   def _renderProviderText(self, report):
      for provider in report['providers']:
         print('  %s' % provider['name'])
         for cause in provider['causes']:
            self._renderCauseText(cause, prefix='   - ')

   def renderText(self, show):
      data = self.data(show)
      for rp in data:
         self._renderCauseText(rp['cause'])
         if show.args.all:
            self._renderProviderText(rp)

class ShowPlatformRebootCause(ShowRebootCause):
   def getData(self, show):
      rcm = getReloadCauseManager(show.platforms[0])
      return self._getData(show, rcm)

class ShowPlatformRebootCauseList(Renderer):
   NAME = 'reboot-cause-list'

   def getData(self, show):
      providers = show.platforms[0].getInventory().getReloadCauseProviders()
      result = []
      for provider in providers:
         result.append({
            # Eventually we should expect a unique name for each provider
            # TODO: verify the names are changed as expected after the update
            # to getSourceName()
            'name': provider.getSourceName(),
            'descs': tuple({
               'code': d.codeStr,
               'type': d.typ,
               'description': d.description,
            } for d in provider.getReloadCauseDescs()),
         })
      return tuple(result)

   def renderText(self, show):
      for provider in self.data(show):
         print(f"Provider: {provider['name']}")
         for desc in provider['descs']:
            print(f"  - {desc['code']} {desc['type']} ({desc['description']})")

class ShowLinecardRebootCause(ShowRebootCause):
   def getData(self, show):
      lcdata = {}
      for linecard, _ in show.inventories:
         rcm = getLinecardReloadCauseManager(linecard)
         lcdata[str(linecard)] = self._getData(show, rcm)
      return lcdata

   def renderText(self, show):
      data = self.data(show)
      for name, lcdata in data.items():
         print(name)
         for rp in lcdata:
            self._renderCauseText(rp['cause'])
            if show.args.all:
               self._renderProviderText(rp)
         print()
