
from functools import cached_property

from arista.core.config import Config
from arista.core.cooling import (
   CoolingFanBase,
   CoolingThermalBase,
)
from arista.core.supervisor import Supervisor

class DBEntity:
   def __init__(self, tbl, name):
      self.tbl = tbl
      self.name = name

   def get_all(self):
      _, data = self.tbl.get(self.name)
      return dict(data)

   def get(self, key):
      _, data = self.tbl.hget(self.name, key)
      return data

class DBMultiEntity:
   def __init__(self, tbls, name):
      self.tbls = tbls
      self.name = name

   def get_all(self, idx=None):
      res = {}
      tbls = [self.tbls[idx]] if idx is not None else self.tbls
      for tbl in tbls:
         _, data = tbl.get(self.name)
         res.update(dict(data))
      return res

   def get(self, key):
      raise NotImplementedError

class DBHelper(object):
   def __init__(self):
      self._dbs = {}
      self._tables = {}
      self._ents = {}

   def _get_db(self, name):
      db = self._dbs.get(name)
      if db is None:
         # pylint: disable=import-error,import-outside-toplevel
         from swsscommon.swsscommon import DBConnector
         db = DBConnector(name, 0, True, '')
         self._dbs[name] = db
      return db

   def _get_ent(self, tname, tbl, name, cls=DBEntity):
      key = (tname, name)
      ent = self._ents.get(key)
      if ent is None:
         ent = cls(tbl, name)
         self._ents[key] = ent
      return ent

   @cached_property
   def _state_db(self):
      return self._get_db('STATE_DB')

   @cached_property
   def _chassis_state_db(self):
      return self._get_db('CHASSIS_STATE_DB')

   def _get_table(self, db, name):
      key = (db, name)
      tbl = self._tables.get(key)
      if tbl is None:
         # pylint: disable=import-error,import-outside-toplevel
         from swsscommon.swsscommon import Table
         tbl = Table(db, name)
         self._tables[key] = tbl
      return tbl

   def _get_table_objects(self, db, name):
      tbl = self._get_table(db, name)
      return [self._get_ent(name, tbl, k) for k in tbl.getKeys()]

   def _get_multi_table_objects(self, db, primary, *others):
      tbl = self._get_table(db, primary)
      tbls = [tbl] + [self._get_table(db, o) for o in others]
      return [self._get_ent(primary, tbls, k, cls=DBMultiEntity)
              for k in tbl.getKeys()]

   def get_all_fans(self):
      return self._get_table_objects(self._state_db, 'FAN_INFO')

   def get_all_psus(self):
      return self._get_table_objects(self._state_db, 'PSU_INFO')

   def get_all_thermals(self):
      return self._get_table_objects(self._state_db, 'TEMPERATURE_INFO')

   def get_all_module_thermals(self, idx):
      tbl = f'TEMPERATURE_INFO_{idx}'
      return self._get_table_objects(self._chassis_state_db, tbl)

   def get_all_xcvrs(self):
      tbls = ['TRANSCEIVER_DOM_SENSOR', 'TRANSCEIVER_DOM_THRESHOLD']
      if Config().cooling_xcvrs_use_dom_temperature:
         tbls += ['TRANSCEIVER_DOM_TEMPERATURE']
      return self._get_multi_table_objects(self._state_db, *tbls)

   def get_all_module_xcvrs(self, idx):
      tbls = (
         f'TRANSCEIVER_DOM_SENSOR_{idx}',
         f'TRANSCEIVER_DOM_THRESHOLD_{idx}',
      )
      return self._get_multi_table_objects(self._chassis_state_db, *tbls)

class EntitySource:
   def __init__(self):
      self.inv = None
      self.api = None
      self.dbent = None

   def register_inv(self, inv):
      if self.inv is None:
         self.inv = inv

   def register_api(self, api):
      if self.api is None:
         self.api = api

   def register_db(self, dbent):
      if self.dbent is None:
         self.dbent = dbent

   def update_from_inv(self):
      return False

   def update_from_api(self):
      return False

   def update_from_db(self):
      return False

   def update(self):
      methods = (
         (self.inv, self.update_from_inv),
         (self.api, self.update_from_api),
         (self.dbent, self.update_from_db),
      )
      for obj, method in methods:
         try:
            if obj and method():
               return True
         except Exception: # pylint: disable=broad-except
            continue
      return False

class CoolingFan(CoolingFanBase, EntitySource):
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.presence = None
      self.status = None

   def update_from_inv(self):
      self.speed = self.inv.getSpeed()
      self.presence = self.inv.getPresence()
      self.status = self.inv.getStatus()
      return True

   def update_from_api(self):
      self.speed = self.api.get_speed()
      self.presence = self.api.get_presence()
      self.status = self.api.get_status()
      return True

   def update_from_db(self):
      # NOTE: fans from db is a bit useless since we need to be able to set
      #       the fan speed from the algorithm
      data = self.dbent.get_all()
      self.speed = int(data['speed_target'])
      self.presence = bool(data['presence'])
      self.status = bool(data['status'])
      return True

class CoolingPsu(EntitySource):
   def __init__(self, name):
      super().__init__()
      self.name = name
      self.presence = None
      self.status = None

   def update_from_inv(self):
      self.presence = self.inv.getPresence()
      self.status = self.inv.getStatus()
      return True

   def update_from_api(self):
      self.presence = self.api.get_presence()
      self.status = self.api.get_status()
      return True

   def update_from_db(self):
      data = self.dbent.get_all()
      self.presence = bool(data['presence'])
      self.status = bool(data['status'])
      return True

class CoolingThermal(CoolingThermalBase, EntitySource):
   # def __init__(self, *args, **kwargs):
   #    super().__init__(*args, **kwargs)
   @property
   def in_overheat_condition(self):
      if not self.temperature or not self.overheat:
         return False
      return self.temperature > self.overheat

   @property
   def in_critical_condition(self):
      if not self.temperature or not self.critical:
         return False
      return self.temperature > self.critical

   def update_from_inv(self):
      self.temperature = self.inv.getTemperature()
      self.overheat = self.inv.getHighThreshold()
      self.critical = self.inv.getHighCriticalThreshold()
      return True

   def update_from_api(self):
      self.temperature = self.api.get_temperature()
      self.overheat = self.api.get_high_threshold()
      self.critical = self.api.get_high_critical_threshold()
      return True

   def update_from_db(self):
      data = self.dbent.get_all()
      self.temperature = float(data['temperature'])
      self.overheat = float(data['high_threshold'])
      self.critical = float(data['critical_high_threshold'])
      return True

class CoolingXcvrThermal(CoolingThermal):
   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self._initialized = False

   @property
   def target(self):
      if Config().cooling_override_xcvr_target is not None:
         return Config().cooling_override_xcvr_target
      if Config().cooling_xcvr_target_offset is not None and self.overheat:
         return self.overheat + Config().cooling_xcvr_target_offset
      return super().target

   def _float_or_none(self, value):
      return float(value) if value not in ['N/A', None] else None

   def update_thresholds(self, thresholds):
      self.overheat = self._float_or_none(thresholds.get('temphighwarning'))
      self.critical = self._float_or_none(thresholds.get('temphighalarm'))

   def update_from_api(self):
      api = self.api.get_xcvr_api()
      if api is None:
         # TODO: something else might need to happen here
         return False
      self.temperature = api.get_module_temperature()
      if not self._initialized:
         if hasattr(api, 'get_transceiver_thresholds_support') and \
            api.get_transceiver_thresholds_support():
            self.update_thresholds(api.get_transceiver_threshold_info())
         self._initialized = True
      return True

   def update_from_db(self):
      for i in ([2, 0] if Config().cooling_xcvrs_use_dom_temperature else [0]):
         data = self.dbent.get_all(i)
         self.temperature = self._float_or_none(data['temperature'])
         if self.temperature is not None:
            break

      if not self._initialized:
         data = self.dbent.get_all(1)
         self.update_thresholds(data)
         self._initialized = True
      return True

class CoolingEntityManager(object):
   def __init__(self, chassis):
      self._chassis = chassis
      self._dbhelper = DBHelper()
      self._gc_seen = set()
      self._gc_count = 0
      self._fans = {}
      self._psus = {}
      self._thermals = {}
      self._xcvrs = {}
      self._xcvrs_via_api = Config().cooling_xcvrs_via_api

   def _get_entity(self, collection, cls, name):
      ent = collection.get(name)
      if ent is None:
         ent = cls(name)
         collection[name] = ent
      self._gc_seen.add(ent)
      return ent

   def get_fan(self, name):
      return self._get_entity(self._fans, CoolingFan, name)

   def get_psu(self, name):
      return self._get_entity(self._psus, CoolingPsu, name)

   def get_thermal(self, name):
      return self._get_entity(self._thermals, CoolingThermal, name)

   def get_xcvr(self, name):
      return self._get_entity(self._thermals, CoolingXcvrThermal, name)

   def get_all_fans(self):
      return self._fans

   def get_all_psus(self):
      return self._psus

   def get_all_thermals(self):
      return self._thermals

   def _iter_inventories(self, chassis):
      platform = chassis.getPlatform()
      yield '', platform.getInventory()
      if isinstance(platform, Supervisor):
         for card in platform.getChassis().iterCards():
            yield f'CARD{card.getSlotId()} ', card.getInventory()
      for slot in platform.getInventory().getPsuSlots():
         if slot.psu:
            yield '', slot.psu.psu.getInventory()

   def _iter_chassis_modules(self, chassis):
      for module in chassis.get_all_modules():
         slotid = module.get_slot()
         if slotid != chassis.get_my_slot():
            yield f'CARD{slotid} ', module

   def _iter_inventory_fans(self, chassis):
      for _, inv in self._iter_inventories(chassis):
         yield from inv.getFans()

   def _iter_chassis_fans(self, chassis):
      if drawers := chassis.get_all_fan_drawers():
         for drawer in drawers:
            yield from drawer.get_all_fans()
      else:
         yield from chassis.get_all_fans()

      for _, module in self._iter_chassis_modules(chassis):
         yield from module.get_all_fans()

      for psu in chassis.get_all_psus():
         yield from psu.get_all_fans()

   def update_fans(self, chassis):
      for fan in self._iter_inventory_fans(chassis):
         self.get_fan(fan.getName()).register_inv(fan)
      for fan in self._iter_chassis_fans(chassis):
         self.get_fan(fan.get_name()).register_api(fan)
      for dbent in self._dbhelper.get_all_fans():
         self.get_fan(dbent.name).register_db(dbent)

   def update_psus(self, chassis):
      for psu in chassis.get_all_psus():
         self.get_psu(psu.get_name()).register_api(psu)
      for dbent in self._dbhelper.get_all_psus():
         # NOTE: psud normalize psu names, convert to internal naming
         name = dbent.name.replace('PSU ', 'psu')
         self.get_psu(name).register_db(dbent)
      # TODO: register internal inventory

   def _iter_inventory_thermals(self, chassis):
      for prefix, inv in self._iter_inventories(chassis):
         for temp in inv.getTemps():
            yield f'{prefix}{temp.getName()}', temp

   def _iter_chassis_thermals(self, chassis):
      for thermal in chassis.get_all_thermals():
         yield thermal.get_name(), thermal
      for prefix, module in self._iter_chassis_modules(chassis):
         for thermal in module.get_all_thermals():
            yield f'{prefix}{thermal.get_name()}', thermal
      for psu in chassis.get_all_psus():
         for thermal in psu.get_all_thermals():
            yield thermal.get_name(), thermal

   def update_thermals(self, chassis):
      for name, ts in self._iter_inventory_thermals(chassis):
         self.get_thermal(name).register_inv(ts)
      for name, thermal in self._iter_chassis_thermals(chassis):
         self.get_thermal(name).register_api(thermal)
      # NOTE: thermalctld publishes card sensor name without namespaces
      #       we need to introduce inventory namespaces which adds a prefix
      #       for now disable querying database for sensors on chassis
      if not chassis.get_num_modules():
         for dbent in self._dbhelper.get_all_thermals():
            self.get_thermal(dbent.name).register_db(dbent)

      for prefix, module in self._iter_chassis_modules(chassis):
         slotid = module.get_slot()
         for dbent in self._dbhelper.get_all_module_thermals(slotid):
            self.get_thermal(f'{prefix}{dbent.name}').register_db(dbent)

   def update_xcvrs(self, chassis):
      # NOTE: inventory cannot read xcvr temperature nor thresholds
      # NOTE: direct api calls are pretty slow and redundant with xcvrd
      #       a setting is therefore needed to enable direct temperature reads
      if self._xcvrs_via_api:
         # NOTE: we have to disable xcvrs from DB when reading via API due to
         # the widely different naming used `EthernetX` vs `osfpY`
         for sfp in chassis.get_all_sfps():
            self.get_xcvr(sfp.get_name()).register_api(sfp)
      else:
         for dbent in self._dbhelper.get_all_xcvrs():
            self.get_xcvr(dbent.name).register_db(dbent)
      # TODO: handle linecard xcvrs
      #       requires xcvr data to be published in CHASSIS_STATE_DB

   def update(self):
      self.update_fans(self._chassis)
      self.update_thermals(self._chassis)
      self.update_psus(self._chassis)
      self.update_xcvrs(self._chassis)

   def dump(self):
      objkeys = ['inv', 'api', 'dbent']
      for col in [self._fans, self._psus, self._thermals, self._xcvrs]:
         for obj in col.values():
            attrs = (f'{a}={bool(getattr(obj, a))}' for a in objkeys)
            print(f'{obj.__class__.__name__} "{obj.name}" {" ".join(attrs)}')

   def gc(self):
      self._gc_count += 1
      if self._gc_count < Config().cooling_gc_count:
         return

      self.update()

      for col in [self._fans, self._psus, self._thermals, self._xcvrs]:
         todelete = []
         for key, obj in col.items():
            if obj not in self._gc_seen:
               todelete.append(key)
         for key in todelete:
            del col[key]

      self._gc_count = 0
      self._gc_seen.clear()

   _ems = {}
   @classmethod
   def get(cls, chassis):
      em = cls._ems.get(chassis)
      if em is None:
         em = cls(chassis)
         em.update()
         cls._ems[chassis] = em
      return em
