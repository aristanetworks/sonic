# Copyright (c) 2026 Arista Networks, Inc.  All rights reserved.
# Arista Networks, Inc. Confidential and Proprietary.

from ..core.daemon import registerDaemonFeature, PollDaemonFeature
from ..core.log import getLogger

logging = getLogger(__name__)

@registerDaemonFeature()
class PsuPresenceFeature(PollDaemonFeature):

   NAME = 'psu'
   INTERVAL = 3

   def _insertPsu(self, psuSlot):
      psu = psuSlot.getLoadedPsu()
      if psu:
         logging.info("%s: PSU %d already exists, but cache is missing.",
                      self, psuSlot.getId())
      psuSlot.reloadPsu()
      psu = psuSlot.getLoadedPsu()
      if psu:
         logging.info("%s: PSU %d has been inserted. Model: %s, Serial number: %s",
                      self, psuSlot.getId(), psu.getModel(), psu.getSerial())
      else:
         logging.info("%s: PSU %d identification failed.", self, psuSlot.getId())

   def _removePsu(self, psuSlot):
      psu = psuSlot.getLoadedPsu()
      if psu is None:
         # Psu object does not exist, but cache exists
         logging.info("%s: PSU %d has previously been removed, clearing cache.",
                      self, psuSlot.getId())
      else:
         logging.info("%s: PSU %d has been removed. Model: %s, "
                      "Serial number: %s",
                      self, psuSlot.getId(), psu.getModel(), psu.getSerial())
      psuSlot.reloadPsu()

   def _processPsuSlot(self, psuSlot):
      slotId = psuSlot.getId()
      presenceNew = psuSlot.getPresence()
      presenceCached = psuSlot.getPresenceCached()

      if presenceNew != presenceCached:
         logging.info("%s: %s presence changed from %s to %s",
                      self, slotId, presenceCached, presenceNew)
      if presenceNew:
         if not presenceCached:
            self._insertPsu(psuSlot)
         else:
            # TODO: check for change in serial number
            pass
      elif presenceCached:
         self._removePsu(psuSlot)

   async def callback(self, elapsed):
      inventory = self.daemon.platform.getInventory()
      for psuSlot in inventory.getPsuSlots():
         self._processPsuSlot(psuSlot)
