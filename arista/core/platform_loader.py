from __future__ import annotations

import importlib
from collections.abc import Iterable, Iterator
from functools import cached_property
from itertools import product
from typing import Generic, TypeVar, TYPE_CHECKING

from arista.core.log import getLogger

if TYPE_CHECKING:
   from arista.core.bmc import Bmc, BmcSubsystem
   from arista.core.cpu import Cpu
   from arista.core.sku import Sku
   from .platform_registry import BaseDescriptor

logger = getLogger(__name__)

PlatformClass = type['Sku']
CpuClass = type['Cpu']
BmcClass = type['Bmc']
BmcSubsystemClass = type['BmcSubsystem']


K = TypeVar("K")
V = TypeVar("V")

class _Index(Generic[K, V]):
   """Stores Vs indexed by Ks. Vs must be `.add`ed first.

   When a K is looked up and is not yet indexed, the K's descriptor is searched
   for in `platform_registry`. This descriptor contains information on the python
   module defining the V. The module is then imported, which - if V is properly
   registered - should result in V being `.add`ed to the index.
   """
   def __init__(self, _loader: _Loader, registry_module: str):
      self._items: list[V] = []
      self._index: dict[K: V] = {}
      self._loader = _loader
      # add prefix for .gitignore
      self._registry_module = f"_auto_{registry_module}"

   def add(self, obj: V) -> V:
      self._items.append(obj)
      for key in self._keysof(obj):
         self._index[key] = obj
      return obj

   def get(self, key: K) -> V | None:
      if not key:
         return None

      if result := self._index.get(key):
         return result

      if desc := self._descriptors.get(key):
         try:
            importlib.import_module(desc.module) # this should populate the index
         except ImportError:
            pass

      if result := self._index.get(key):
         return result

      # As a final fallback, try full discovery
      logger.warning("Running full platform discovery in search for '%s'", key)
      self._loader._discover_all()  # pylint: disable=protected-access

      return self._index.get(key)

   def _keysof(self, obj: V) -> Iterable[K]:
      raise NotImplementedError

   def keys(self) -> Iterable[K]:
      if self._descriptors:
         return self._descriptors.keys()
      self._loader._discover_all()  # pylint: disable=protected-access
      return self._index.keys()

   @cached_property
   def _descriptors(self) -> dict[K, BaseDescriptor[K]]:
      result: dict[K, BaseDescriptor[K]] = {}
      for desc in self._load_registry():
         for key in desc.keys:
            result[key] = desc
      return result

   def _load_registry(self) -> Iterable[BaseDescriptor[K]]:
      try:
         registry = importlib.import_module(
            f"arista.core.platform_registry.{self._registry_module}"
         )
         return getattr(registry, "DESCRIPTORS", [])
      except ImportError:
         return []


class PlatformIndex(_Index[str, PlatformClass]):
   def _keysof(self, obj: PlatformClass) -> Iterator[str]:
      """Keeps SKUs and SIDs in the same index; assumes that SKUs and SIDs
      are unique (or identify the same platform).
      """
      yield from obj.SID
      yield from obj.SKU
      if obj.PLATFORM:
         yield obj.PLATFORM

class CpuIndex(_Index[str, CpuClass]):
   def _keysof(self, obj: CpuClass) -> Iterable[str]:
      yield from obj.SID
      if obj.PLATFORM:
         yield obj.PLATFORM

class BmcIndex(_Index[str, BmcClass]):
   def _keysof(self, obj: BmcClass) -> Iterable[str]:
      return obj.MODEL

class BmcSubsystemIndex(_Index[tuple[str, str], BmcSubsystemClass]):
   def _keysof(self, obj: BmcSubsystemClass) -> Iterable[tuple[str, str]]:
      return product(obj.BMC_CLS.MODEL, obj.HOST_SWITCH_CLS.SID)


class _Loader:
   def __init__(self):
      self.platforms = PlatformIndex(self, "platforms")
      self.cpus = CpuIndex(self, "cpus")
      self.bmcs = BmcIndex(self, "bmcs")
      self.bmc_subsystems = BmcSubsystemIndex(self, "bmc_subsystems")

   def _indexes(self) -> Iterable[_Index]:
      return (self.platforms, self.cpus, self.bmcs, self.bmc_subsystems)

   _did_run_discovery = False
   def _discover_all(self):
      """Load all possible platforms by importing submodules."""
      if not self._did_run_discovery:
         self._did_run_discovery = True
         # pylint: disable=import-outside-toplevel
         from arista.core.dynload import importSubmodules
         importSubmodules('arista.platforms')

   def all_platforms(self) -> Iterable[PlatformClass]:
      self._discover_all()
      yield from self.platforms._items  # pylint: disable=protected-access

platform_loader = _Loader()
