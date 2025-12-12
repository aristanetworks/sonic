
class DenaliAsicDesc(object):
   def __init__(self, cls=None, asicId=0, dieId=0, rstIdx=None):
      self.cls = cls
      self.asicId = asicId
      self.dieId = dieId
      self.rstIdx = rstIdx or asicId
