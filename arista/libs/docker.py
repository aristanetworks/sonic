import os.path

def runningInContainer():
   # Docker containers by default have this path.
   return os.path.exists("/.dockerenv")
