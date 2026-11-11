import re
import shutil

from . import http
from .paths import cache_dir

FOLDER = "WowamCompanion"
API = "https://data.wago.io/api"
URL = re.compile(r'\["url"\] = "https?://wago\.io/([^/"\s]+)(?:/(\d+))?[^"]*"')


def local(client):
    found = {}
    for path in client.wtf_dir.glob("Account/*/SavedVariables/WeakAuras.lua"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for slug, version in URL.findall(text):
            version = int(version or 1)
            found[slug] = min(found.get(slug, version), version)
    return found


def check(slugs):
    out = []
    ids = sorted(slugs)
    for i in range(0, len(ids), 80):
        try:
            data = http.get_json(f"{API}/check/weakauras?ids={','.join(ids[i:i + 80])}", max_age=600)
        except http.HttpError:
            continue
        for entry in data if isinstance(data, list) else []:
            for key in (entry.get("slug"), entry.get("_id")):
                if key in slugs and int(entry.get("version") or 0) > slugs[key]:
                    out.append((key, entry))
                    break
    return out


def encoded(entry):
    target = cache_dir() / "auras" / f"{entry['_id']}-{entry['version']}"
    try:
        return target.read_text()
    except OSError:
        pass
    try:
        http.download(f"{API}/raw/encoded?id={entry['_id']}", target)
        return target.read_text()
    except (http.HttpError, OSError):
        return ""


def quote(text):
    text = str(text or "")
    level = 1
    while "]" + "=" * level + "]" in text or text.endswith("]" + "=" * level):
        level += 1
    eq = "=" * level
    return f"[{eq}[{text}]{eq}]"


def render(updates):
    lines = ["WowamCompanionData = {", "  slugs = {"]
    for key, entry, text in updates:
        note = (entry.get("changelog") or {}).get("text", "")
        lines += [
            f"    [ {quote(key)} ] = {{",
            f"      name = {quote(entry.get('name'))},",
            f"      author = {quote(entry.get('username'))},",
            f"      encoded = {quote(text)},",
            f"      wagoVersion = {quote(entry.get('version'))},",
            f"      wagoSemver = {quote(entry.get('versionString'))},",
            f"      source = {quote('Wago')},",
            f"      versionNote = {quote(note)},",
            "    },",
        ]
    lines += ["  },", "  stash = {},", "}", ""]
    return "\n".join(lines)


INIT = """if WeakAuras and WeakAuras.AddCompanionData and WowamCompanionData then
  WeakAuras.AddCompanionData(WowamCompanionData)
end
"""


def write(client, updates):
    folder = client.addons_dir / FOLDER
    if not updates and not folder.exists():
        return
    toc = (
        f"## Interface: {client.interface or 0}\n"
        "## Title: WoW Addon Manager Companion\n"
        "## Notes: Hands WeakAuras updates found by WoW Addon Manager to WeakAuras\n"
        "## Dependencies: WeakAuras\n"
        "## Version: 1\n"
        "Data.lua\n"
        "Init.lua\n"
    )
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in ((f"{FOLDER}.toc", toc), ("Init.lua", INIT), ("Data.lua", render(updates))):
        path = folder / name
        try:
            if path.read_text() == text:
                continue
        except OSError:
            pass
        path.write_text(text)


def remove(client):
    shutil.rmtree(client.addons_dir / FOLDER, ignore_errors=True)


def sync(client):
    if not (client.addons_dir / "WeakAuras").is_dir():
        return []
    slugs = local(client)
    updates = []
    for key, entry in check(slugs) if slugs else []:
        text = encoded(entry)
        if text:
            updates.append((key, entry, text))
    write(client, updates)
    return [
        {"name": entry.get("name") or key, "old": slugs[key], "new": int(entry["version"])}
        for key, entry, _ in updates
    ]
