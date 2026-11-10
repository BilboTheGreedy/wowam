import json
import os


class State:
    def __init__(self, client):
        self.path = client.wtf_dir / "wowam.json"
        self.addons = {}
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text())
            addons = data.get("addons", {})
            self.addons = addons if isinstance(addons, dict) else {}
        except (OSError, ValueError, AttributeError):
            self.addons = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "addons": self.addons}, indent=2))
        os.replace(tmp, self.path)
