
import os
import subprocess

def ping(address):
   cmd = ['ping', '-c', '1', '-W', '1', address]
   try:
      with open(os.devnull, 'wb') as devnull:
         return subprocess.call(cmd, stdout=devnull, stderr=devnull) == 0
   except subprocess.CalledProcessError:
      return False
