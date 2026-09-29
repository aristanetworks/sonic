from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import product
from typing import Generic, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
   from arista.core.bmc import Bmc, BmcSubsystem
   from arista.core.cpu import Cpu
   from arista.core.sku import Sku

PlatformClass = type['Sku']
CpuClass = type['Cpu']
BmcClass = type['Bmc']
BmcSubsystemClass = type['BmcSubsystem']


K = TypeVar("K")
V = TypeVar("V")

class _Index(Generic[K, V]):
   def __init__(self, _loader: _Loader):
      self._items: list[V] = []
      self._index: dict[K: V] = {}
      self._loader = _loader

   def add(self, obj: V) -> V:
      self._items.append(obj)
      for key in self._keysof(obj):
         self._index[key] = obj
      return obj

   def get(self, key: K) -> V | None:
      self._loader._discover_all()  # pylint: disable=protected-access
      return self._index.get(key)

   def _keysof(self, obj: V) -> Iterable[K]:
      raise NotImplementedError

   def keys(self) -> Iterable[K]:
      self._loader._discover_all()  # pylint: disable=protected-access
      return self._index.keys()

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
      self.platforms = PlatformIndex(self)
      self.cpus = CpuIndex(self)
      self.bmcs = BmcIndex(self)
      self.bmc_subsystems = BmcSubsystemIndex(self)

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
