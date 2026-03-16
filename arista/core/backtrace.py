
import sys
import traceback

def excepthookExtended(typ, value, tb):
   """
   Print the usual traceback information, followed by a listing of all the
   local variables in each frame.
   """
   traceback.print_exception(typ, value, tb)
   while True:
      if not tb.tb_next:
         break
      tb = tb.tb_next
   stack = []
   f = tb.tb_frame
   while f:
      stack.append(f)
      f = f.f_back
   stack.reverse()
   print("Locals by frame, innermost last")
   for frame in stack:
      print()
      print("Frame %s in %s at line %s" % (frame.f_code.co_name,
            frame.f_code.co_filename,
            frame.f_lineno))
      for key, val in frame.f_locals.items():
         print("\t%20s = " % key, end='')
         # We have to be careful not to cause a new error in our error
         # printer! Calling str() on an unknown object could cause an
         # error we don't want.
         try:
            print(val)
         except Exception: # pylint: disable=broad-except
            print("<ERROR WHILE PRINTING VALUE>")

def loadBacktraceHook():
   sys.excepthook = excepthookExtended
