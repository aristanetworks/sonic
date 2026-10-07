from dataclasses import dataclass

from typing import Generic, TypeVar

K = TypeVar("K")

@dataclass(frozen=True, slots=True)
class BaseDescriptor(Generic[K]):
   """For a given set of keys, store the associated module path."""
   module: str
   keys: tuple[K, ...]
