import os
import sys
from pathlib import Path

APP = "wowam"
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"


def _env(var):
    value = os.environ.get(var)
    return Path(value) if value else None


def config_home():
    found = _env("XDG_CONFIG_HOME")
    if found:
        return found
    if WIN:
        return _env("APPDATA") or Path.home() / "AppData" / "Roaming"
    if MAC:
        return Path.home() / "Library" / "Application Support"
    return Path.home() / ".config"


def data_home():
    found = _env("XDG_DATA_HOME")
    if found:
        return found
    if WIN:
        return _env("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    if MAC:
        return Path.home() / "Library" / "Application Support"
    return Path.home() / ".local" / "share"


def config_dir():
    return config_home() / APP


def data_dir():
    return data_home() / APP


def cache_dir():
    found = _env("XDG_CACHE_HOME")
    if found:
        return found / APP
    if WIN:
        return data_home() / APP / "cache"
    if MAC:
        return Path.home() / "Library" / "Caches" / APP
    return Path.home() / ".cache" / APP
