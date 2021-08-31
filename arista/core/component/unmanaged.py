
from .component import Component
from ..utils import NoopObj

class UnmanagedComponent(Component):
   DRIVER = NoopObj
