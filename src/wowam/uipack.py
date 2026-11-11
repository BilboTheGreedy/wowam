import json
import re
import shutil
import time
import zipfile
from pathlib import Path

from . import backup, installer
from .sources import SourceError

MANIFEST = "wowam-ui.json"
ACCOUNT, REALM, CHAR = "ACCOUNT", "Realm", "Character"
SKIP_DIRS = {"SavedVariables"}


def _parts(name):
    return [p for p in name.replace("\\", "/").split("/") if p]


def _safe(parts):
    return bool(parts) and ".." not in parts and ":" not in parts[0]


def _wtf(parts):
    low = [p.lower() for p in parts]
    for i in range(len(low) - 1):
        if low[i] == "wtf" and low[i + 1] == "account":
            return parts[i + 2:]
    return None


def _addon(parts):
    low = [p.lower() for p in parts]
    for i in range(len(low) - 1):
        if low[i] == "interface" and low[i + 1] == "addons":
            return parts[i + 2:]
    return None


def chars(client):
    out = []
    root = client.wtf_dir / "Account"
    try:
        accounts = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return out
    for acct in accounts:
        for realm in sorted(p for p in acct.iterdir() if p.is_dir() and p.name not in SKIP_DIRS):
            for char in sorted(p for p in realm.iterdir() if p.is_dir()):
                out.append((acct.name, realm.name, char.name))
    return out


def inspect(path):
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return None
    with zf:
        meta = {}
        found = set()
        accounts = set()
        bundled = set()
        files = 0
        for info in zf.infolist():
            parts = _parts(info.filename)
            if not _safe(parts) or info.is_dir():
                continue
            if parts[-1] == MANIFEST and len(parts) <= 2:
                try:
                    meta = json.loads(zf.read(info))
                except ValueError:
                    meta = {}
                continue
            rest = _wtf(parts)
            if rest and len(rest) >= 3 and rest[-2] == "SavedVariables":
                files += 1
                accounts.add(rest[0])
                if len(rest) == 5:
                    found.add((rest[0], rest[1], rest[2]))
                continue
            rest = _addon(parts)
            if rest and len(rest) >= 2:
                bundled.add(rest[0])
        if not files and not isinstance(meta.get("addons"), list):
            return None
        refs = [r for r in meta.get("addons", []) if isinstance(r, str)] if isinstance(meta, dict) else []
        return {
            "name": str(meta.get("name") or Path(path).stem)[:80],
            "by": str(meta.get("by") or "")[:60],
            "game": str(meta.get("game") or "")[:40],
            "addons": refs,
            "bundled": sorted(bundled),
            "chars": sorted(found),
            "accounts": sorted(accounts),
            "files": files,
        }


def rename(text, src, dst):
    pairs = []
    s_realm, s_char = src[1], src[2]
    d_realm, d_char = dst[1], dst[2]
    if s_char and s_realm:
        flat_s, flat_d = s_realm.replace(" ", ""), d_realm.replace(" ", "")
        pairs += [
            (f"{s_char} - {s_realm}", f"{d_char} - {d_realm}"),
            (f"{s_char}-{s_realm}", f"{d_char}-{d_realm}"),
            (f"{s_char}-{flat_s}", f"{d_char}-{flat_d}"),
            (f"{s_char} - {flat_s}", f"{d_char} - {flat_d}"),
        ]
    if len(s_char) >= 3:
        pairs.append((f'"{s_char}"', f'"{d_char}"'))
    if len(s_realm) >= 3:
        pairs.append((f'"{s_realm}"', f'"{d_realm}"'))
    for old, new in pairs:
        if old != new:
            text = text.replace(old, new)
    return text


def _write(zf, info, target, src, dst):
    target.parent.mkdir(parents=True, exist_ok=True)
    data = zf.read(info)
    if target.suffix.lower() == ".lua":
        try:
            data = rename(data.decode("utf-8"), src, dst).encode("utf-8")
        except UnicodeDecodeError:
            pass
    target.write_bytes(data)


def apply(client, path, src, dst, keep=7):
    if not all(dst) or any("/" in p or "\\" in p or p in (".", "..") for p in dst):
        raise SourceError("Pick one of your characters first")
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise SourceError("That file is not a valid zip file.") from e
    with zf:
        backup.create(client, keep)
        account = client.wtf_dir / "Account" / dst[0]
        settings = 0
        addons = {}
        for info in zf.infolist():
            parts = _parts(info.filename)
            if not _safe(parts) or info.is_dir():
                continue
            rest = _wtf(parts)
            if rest and len(rest) >= 3 and rest[-2] == "SavedVariables":
                if not rest[-1].lower().endswith(".lua") or rest[0] != src[0]:
                    continue
                if len(rest) == 3:
                    _write(zf, info, account / "SavedVariables" / rest[-1], src, dst)
                    settings += 1
                elif len(rest) == 5 and (rest[1], rest[2]) == (src[1], src[2]):
                    _write(zf, info, account / dst[1] / dst[2] / "SavedVariables" / rest[-1], src, dst)
                    settings += 1
                continue
            rest = _addon(parts)
            if rest and len(rest) >= 2:
                addons.setdefault(rest[0], []).append((info, rest))
        tmp = client.addons_dir / f".wowam-tmp-{time.monotonic_ns()}"
        try:
            for name, members in addons.items():
                if name.startswith("."):
                    continue
                for info, rest in members:
                    target = tmp.joinpath(*rest)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as f, open(target, "wb") as out:
                        shutil.copyfileobj(f, out)
                installer.remove(client.addons_dir / name)
                shutil.move(str(tmp / name), str(client.addons_dir / name))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return {"settings": settings, "addons": sorted(addons)}


def scrub(text, src):
    return rename(text, src, (ACCOUNT, REALM, CHAR))


def export(client, src, folders, refs, dest, name, by=""):
    account = client.wtf_dir / "Account" / src[0]
    wanted = {f.lower() for f in folders}
    picks = []
    for base, arc in (
        (account / "SavedVariables", f"WTF/Account/{ACCOUNT}/SavedVariables"),
        (account / src[1] / src[2] / "SavedVariables", f"WTF/Account/{ACCOUNT}/{REALM}/{CHAR}/SavedVariables"),
    ):
        try:
            found = sorted(p for p in base.iterdir() if p.suffix.lower() == ".lua" and p.stem.lower() in wanted)
        except OSError:
            found = []
        picks += [(p, f"{arc}/{p.name}") for p in found]
    if not picks:
        raise SourceError("That character has no saved addon settings yet")
    dest.parent.mkdir(parents=True, exist_ok=True)
    meta = {"name": name, "by": by, "game": client.label, "addons": list(refs), "version": 1}
    tmp = dest.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST, json.dumps(meta, indent=2))
        for path, arc in picks:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            zf.writestr(arc, scrub(text, src))
    tmp.replace(dest)
    return {"path": dest, "files": len(picks)}
