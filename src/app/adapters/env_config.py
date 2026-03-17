"""Adapter: EnvConfig (hexagonal, SOLID).

Implements Config interface using environment variables.
"""
import os
from ..core.config import Config

class EnvConfig(Config):
    def get(self, key: str, default=None):
        return os.getenv(key, default)

    def get_list(self, key: str, sep: str = ",", default=None):
        val = os.getenv(key)
        if val is None:
            return default if default is not None else []
        return [v.strip() for v in val.split(sep) if v.strip()]
