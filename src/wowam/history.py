import json
import os
import time

from .paths import data_dir

KEEP = 200


def path():
    return data_dir() / "history.json"


def entries():
    try:
        data = json.loads(path().read_text())
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def add(client, name, old, new):
    rows = entries()
    rows.insert(0, {"time": int(time.time()), "client": client, "name": name, "old": old, "new": new})
    target = path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows[:KEEP]))
        os.replace(tmp, target)
    except OSError:
        pass
