
import json
import socket

from ...core.log import getLogger
from ...core.utils import simulateWith
from ...inventory.watchdog import Watchdog

logging = getLogger(__name__)

class AspeedWatchdog(Watchdog):
   """IPC client to the hw-watchdog-mgrd daemon for Aspeed BMC platforms.

   The hw-watchdog-mgrd daemon is the sole owner of /dev/watchdog0 and exposes
   arm/disarm/status over a Unix domain socket. This class implements the
   arista inventory Watchdog interface as a thin IPC client.

   All timeouts in this class are in centiseconds (arista inventory convention).
   The daemon works in seconds, so conversions happen at the boundary.
   """

   SOCKET_PATH = "/run/hw-watchdog-mgrd/hw-watchdog-mgrd.sock"
   SOCKET_TIMEOUT = 5
   SYSFS_BASE = '/sys/class/watchdog/watchdog0'
   MAX_TIMEOUT = 30000 # 300 seconds in centiseconds

   def _request(self, req):
      sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      sock.settimeout(self.SOCKET_TIMEOUT)
      try:
         sock.connect(self.SOCKET_PATH)
         sock.sendall((json.dumps(req) + '\n').encode())
         data = sock.recv(4096)
      finally:
         sock.close()
      return json.loads(data.decode().strip())

   def _readSysfs(self, name):
      path = '%s/%s' % (self.SYSFS_BASE, name)
      with open(path, 'r', encoding='utf-8') as f:
         return f.read().strip()

   def _sysfsIsArmed(self):
      return self._readSysfs('state') == 'active'

   def _sysfsTimeout(self):
      try:
         return int(self._readSysfs('timeout')) * 100
      except (ValueError, OSError):
         return 0

   def armSim(self, timeout):
      if timeout > self.MAX_TIMEOUT:
         logging.error('watchdog timeout %s exceeds max timeout %s',
                       timeout, self.MAX_TIMEOUT)
         return False
      if timeout < 0:
         logging.error('watchdog timeout %s must be positive', timeout)
         return False
      logging.info('watchdog arm timeout=%s', timeout)
      return True

   @simulateWith(armSim)
   def arm(self, timeout):
      if timeout > self.MAX_TIMEOUT:
         logging.error('watchdog timeout %s exceeds max timeout %s',
                       timeout, self.MAX_TIMEOUT)
         return False

      seconds = timeout // 100
      resp = self._request({'cmd': 'arm', 'seconds': seconds})
      if resp.get('result', -1) < 0:
         logging.error('watchdog arm failed')
         return False
      logging.info('watchdog armed timeout=%ds', seconds)
      return True

   def stopSim(self):
      logging.info('watchdog stop')
      return True

   @simulateWith(stopSim)
   def stop(self):
      resp = self._request({'cmd': 'disarm'})
      if not resp.get('result', False):
         logging.error('watchdog stop failed')
         return False
      logging.info('watchdog stopped')
      return True

   def statusSim(self):
      logging.info('watchdog status')
      return {'enabled': True, 'timeout': 300, 'remainingTime': 100}

   @simulateWith(statusSim)
   def status(self):
      try:
         armed = self._request({'cmd': 'is_armed'})
         enabled = bool(armed.get('result', False))
      except (OSError, ValueError):
         # Daemon unreachable — fall back to sysfs so status reflects hardware
         # truth (e.g. daemon crashed while watchdog is armed). Remaining time
         # is unavailable since sysfs does not expose timeleft on this device.
         return {
            'enabled': self._sysfsIsArmed(),
            'timeout': self._sysfsTimeout(),
            'remainingTime': -1,
         }

      if not enabled:
         return {
            'enabled': False,
            'timeout': 0,
            'remainingTime': -1,
         }

      remaining = self._request({'cmd': 'get_remaining_time'})
      timeout = self._request({'cmd': 'get_timeout'})

      remainingSeconds = remaining.get('result', -1)
      timeoutSeconds = timeout.get('result', 0)

      return {
         'enabled': True,
         'timeout': timeoutSeconds * 100,
         'remainingTime': remainingSeconds * 100 if remainingSeconds >= 0 else -1,
      }
