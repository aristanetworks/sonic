
from .i2c import I2cDevDriver
from .kernel import I2cKernelDriver

class PsuPmbusDetect(I2cDevDriver):

   MFR_ID = 0x99
   MFR_MODEL = 0x9a
   MFR_REVISION = 0x9b
   MFR_LOCATION = 0x9c
   MFR_DATE = 0x9d
   MFR_SERIAL = 0x9e

   UNKNOWN_METADATA = {
      key : 'N/A'
      for key in ['id', 'model', 'revision', 'location', 'date', 'serial']
   }

   def __init__(self, addr):
      super(PsuPmbusDetect, self).__init__(name='pmbus-detect', addr=addr)
      self.addr = addr
      self.id_ = None
      self.model_ = None
      self.revision_ = None
      self.location_ = None
      self.date_ = None
      self.serial_ = None

      self._prepare()

   def _prepare(self):
      try:
         # init device on page 0
         self.write_byte_data(0x00, 0x00)
      except Exception: # pylint: disable=broad-except
         pass

   def id(self):
      if self.id_ is None:
         self.id_ = self.read_block_data_str(self.MFR_ID)
      return self.id_

   def model(self):
      if self.model_ is None:
         self.model_ = self.read_block_data_str(self.MFR_MODEL)
      return self.model_

   def revision(self):
      if self.revision_ is None:
         try:
            self.revision_ = self.read_block_data_str(self.MFR_REVISION)
         except IOError:
            self.revision_ = "N/A"
      return self.revision_

   def location(self):
      if self.location_ is None:
         try:
            self.location_ = self.read_block_data_str(self.MFR_LOCATION)
         except IOError:
            self.location_ = "N/A"
      return self.location_

   def date(self):
      if self.date_ is None:
         try:
            self.date_ = self.read_block_data_str(self.MFR_DATE)
         except IOError:
            self.date_ = "N/A"
      return self.date_

   def serial(self):
      if self.serial_ is None:
         try:
            self.serial_ = self.read_block_data_str(self.MFR_SERIAL)
         except IOError:
            self.serial_ = "N/A"
      return self.serial_

   def getMetadata(self):
      return {
         'id': self.id(),
         'model': self.model(),
         'revision': self.revision(),
         'location': self.location(),
         'date': self.date(),
         'serial': self.serial(),
      }

class PmbusKernelDriver(I2cKernelDriver):
   MODULE = 'pmbus'
   NAME = 'pmbus'
