
class ActionError(Exception):
   def __init__(self, msg, code=1):
      self.code = code
      self.msg = msg

   def __str__(self):
      return '%s: %s (code %d)' % (self.__class__.__name__, self.msg, self.code)

class ActionComplete(ActionError):
   def __init__(self, msg='action completed early', code=0):
      super(ActionComplete, self).__init__(msg=msg, code=code)
