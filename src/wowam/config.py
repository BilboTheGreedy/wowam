import json
import os

from .paths import config_dir

DEFAULTS = {
    "extra_paths": [],
    "github_token": "",
    "wago_key": "",
    "backup_keep": 7,
    "backup_on_update": True,
    "last_client": "",
    "check_updates": True,
    "update_on_start": False,
    "browse_listed": "",
    "theme": "",
    "curseforge_key": "",
    "tray": False,
    "aura_updates": True,
}


class Config:
    def __init__(self):
        self.path = config_dir() / "config.json"
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            loaded = json.loads(self.path.read_text())
        except (OSError, ValueError):
            loaded = {}
        for key, value in DEFAULTS.items():
            got = loaded.get(key, value)
            self.data[key] = got if isinstance(got, type(value)) else value

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()
