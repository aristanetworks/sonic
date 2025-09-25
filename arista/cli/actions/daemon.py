
from __future__ import absolute_import, division, print_function

from . import registerAction
from ..args.daemon import daemonParser
from ...core.log import getLogger
from ...core.daemon import Daemon, getDaemonFeatureCls
from ...core.supervisor import Supervisor

logging = getLogger(__name__)

@registerAction(daemonParser)
def doDaemon(ctx, args):
   if isinstance(ctx.platform, Supervisor):
      ctx.platform.getChassis().loadAll()
   daemon = Daemon(ctx.platform)
   for featureCls in getDaemonFeatureCls(args.feature, args.skip_feature):
      if featureCls.runnable(daemon):
         logging.debug('daemon: loading feature %s', featureCls.NAME)
         daemon.addFeature(featureCls())
      else:
         logging.debug('daemon: skipping feature %s', featureCls.NAME)
   daemon.run()
