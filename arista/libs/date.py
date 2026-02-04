
import datetime
from time import time
from arista.libs.python import monotonicRaw

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def datetimeToStr(dt, fmt=DATE_FORMAT):
   return dt.strftime(fmt)

def strToDatetime(s, fmt=DATE_FORMAT):
   return datetime.datetime.strptime(s, fmt)

def epochToDatetime(epoch):
   return datetime.datetime.fromtimestamp(epoch)

def redisLastUpdateTimeToMonotonic( redisTime ):
   now_mono = monotonicRaw()
   now_wall = time()
   timestamp = None
   wall_timestamp = strToDatetime( redisTime, "%a %b %d %H:%M:%S %Y"
      ).replace(tzinfo=datetime.timezone.utc).timestamp()
   timestamp = wall_timestamp + (now_mono - now_wall)
   return timestamp
