import os
import shutil
import time
import zipfile

from .paths import data_dir

SKIP = {"wowam.json", "wowam.tmp"}


def folder(client):
    return data_dir() / "backups" / client.id


def entries(client):
    try:
        files = sorted(folder(client).glob("*.zip"), reverse=True)
    except OSError:
        return []
    return [{"name": f.name, "size": f.stat().st_size, "time": f.stat().st_mtime} for f in files]


def create(client, keep=7):
    wtf = client.wtf_dir
    if not wtf.is_dir():
        return None
    dest = folder(client)
    dest.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    target = dest / f"{stamp}.zip"
    n = 1
    while target.exists():
        n += 1
        target = dest / f"{stamp}-{n}.zip"
    tmp = target.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for base, dirs, files in os.walk(wtf):
            dirs.sort()
            for name in sorted(files):
                if name in SKIP:
                    continue
                full = os.path.join(base, name)
                try:
                    zf.write(full, os.path.relpath(full, wtf))
                except OSError:
                    pass
    os.replace(tmp, target)
    if keep > 0:
        for old in sorted(dest.glob("*.zip"), reverse=True)[keep:]:
            old.unlink()
    return target


def restore(client, name):
    source = folder(client) / os.path.basename(name)
    if not source.is_file():
        raise FileNotFoundError(name)
    wtf = client.wtf_dir
    with zipfile.ZipFile(source) as zf:
        for info in zf.infolist():
            parts = [p for p in info.filename.replace("\\", "/").split("/") if p]
            if info.filename.startswith("/") or ".." in parts:
                raise ValueError("unsafe path in backup")
        create(client, keep=0)
        wtf.mkdir(parents=True, exist_ok=True)
        for child in wtf.iterdir():
            if child.name in SKIP:
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        zf.extractall(wtf)
