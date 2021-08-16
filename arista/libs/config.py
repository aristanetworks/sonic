
def parseKeyValueConfig(path, keysep='=', commentchr='#'):
   data = {}
   with open(path) as f:
      for line in f.readlines():
         line = line.rstrip()
         if not line or line.startswith(commentchr):
            continue
         k, v = line.split(keysep, 1)
         data[k] = v
   return data
