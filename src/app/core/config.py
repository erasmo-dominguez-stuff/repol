"""Port: Config interface (hexagonal, SOLID).

Defines the interface for configuration providers.
"""
from abc import ABC, abstractmethod

class Config(ABC):
    @abstractmethod
    def get(self, key: str, default=None):
        pass

    @abstractmethod
    def get_list(self, key: str, sep: str = ",", default=None):
        pass
