import os
from pathlib import Path

APP = "wowam"


def _xdg(var, default):
    value = os.environ.get(var)
    return Path(value) if value else Path.home() / default


def config_home():
    return _xdg("XDG_CONFIG_HOME", ".config")


def data_home():
    return _xdg("XDG_DATA_HOME", ".local/share")


def config_dir():
    return config_home() / APP


def cache_dir():
    return _xdg("XDG_CACHE_HOME", ".cache") / APP


def data_dir():
    return data_home() / APP
