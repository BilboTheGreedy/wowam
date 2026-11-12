import hashlib
import os
import shutil
import time
import zipfile
from collections import Counter

from .toc import strip_suffix


class InstallError(Exception):
    pass


def _files(path):
    out = []
    for base, dirs, files in os.walk(path):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(base, name)
            out.append((os.path.relpath(full, path).replace(os.sep, "/"), full))
    return out


def dir_hash(path):
    h = hashlib.sha256()
    for rel, full in _files(path):
        h.update(rel.encode("utf-8", "replace"))
        h.update(b"\0")
        try:
            with open(full, "rb") as f:
                while chunk := f.read(1 << 20):
                    h.update(chunk)
        except OSError:
            h.update(b"?")
        h.update(b"\0")
    return h.hexdigest()


def dir_stamp(path):
    h = hashlib.sha1()
    for rel, full in _files(path):
        try:
            st = os.stat(full)
            h.update(f"{rel}\0{st.st_size}\0{st.st_mtime_ns}\0".encode("utf-8", "replace"))
        except OSError:
            h.update(f"{rel}\0?\0".encode("utf-8", "replace"))
    return h.hexdigest()


def remove(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _extract(zf, dest):
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        parts = [p for p in name.split("/") if p]
        if name.startswith("/") or ".." in parts or (parts and ":" in parts[0]):
            raise InstallError("The archive contains an unsafe path.")
        if not parts:
            continue
        target = dest.joinpath(*parts)
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)


def _toc_stems(folder):
    return [strip_suffix(p.stem) for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".toc"]


def _raw_stems(folder):
    return [p.stem for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".toc"]


def _locate(folder, depth=0):
    stems = _toc_stems(folder)
    if stems:
        if folder.name in stems or folder.name in _raw_stems(folder):
            return {folder.name: folder}
        return {Counter(stems).most_common(1)[0][0]: folder}
    dirs = [p for p in folder.iterdir() if p.is_dir()]
    found = {}
    for d in dirs:
        stems = _toc_stems(d)
        if not stems:
            continue
        if d.name in stems or d.name in _raw_stems(d) or len(dirs) > 1:
            found[d.name] = d
        else:
            found[Counter(stems).most_common(1)[0][0]] = d
    if found:
        return found
    if len(dirs) == 1 and depth < 2:
        return _locate(dirs[0], depth + 1)
    return {}


def install_zip(zip_path, addons_dir):
    addons_dir.mkdir(parents=True, exist_ok=True)
    tmp = addons_dir / f".wowam-tmp-{os.getpid()}-{time.monotonic_ns()}"
    tmp.mkdir()
    try:
        try:
            with zipfile.ZipFile(zip_path) as zf:
                _extract(zf, tmp)
        except zipfile.BadZipFile as e:
            raise InstallError("The download is not a valid zip file.") from e
        located = _locate(tmp)
        if not located:
            raise InstallError("No addon was found in the archive.")
        names = []
        for name, src in sorted(located.items()):
            dst = addons_dir / name
            remove(dst)
            shutil.move(str(src), str(dst))
            names.append(name)
        return names
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
