import re

LOAD = re.compile(r"AddOn \[([^\]]+)\] (?:failure to load: (\w+)|Failed to load missing dependency \[([^\]]+)\])")
MESSAGE = re.compile(r'\["message"\] = "((?:[^"\\]|\\.)*)"')
FOLDER = re.compile(r"Interface[/\\]+AddOns[/\\]+([^/\\:\"]+)", re.I)


def _read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace"), path.stat().st_mtime
    except OSError:
        return "", 0


def problems(client):
    out = {}

    def entry(name, stamp):
        item = out.setdefault(name.lower(), {"errors": 0, "load": "", "time": 0})
        item["time"] = max(item["time"], stamp)
        return item

    text, stamp = _read(client.path / "Logs" / "FrameXML.log")
    for m in LOAD.finditer(text):
        entry(m.group(1), stamp)["load"] = f"needs {m.group(3)}" if m.group(3) else m.group(2)
    try:
        files = list((client.wtf_dir / "Account").glob("*/SavedVariables/!BugGrabber.lua"))
    except OSError:
        files = []
    for path in files:
        text, stamp = _read(path)
        for m in MESSAGE.finditer(text):
            hit = FOLDER.search(m.group(1))
            if hit:
                entry(hit.group(1), stamp)["errors"] += 1
    return out


def for_addon(found, dirs, since=0):
    errors, load = 0, ""
    for d in dirs:
        item = found.get(d.lower())
        if not item or item["time"] <= since:
            continue
        errors += item["errors"]
        load = load or item["load"]
    if load:
        return f"Did not load in the game: {load}"
    if errors:
        return "1 error in the game" if errors == 1 else f"{errors} errors in the game"
    return ""
