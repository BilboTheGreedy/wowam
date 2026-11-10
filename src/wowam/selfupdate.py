import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from . import __version__, http
from .paths import MAC, WIN, cache_dir

REPO = "BilboTheGreedy/wowam"
ASSETS = {"windows": "wowam-setup.exe", "linux": "wowam-linux-x86_64.tar.gz"}


class UpdateError(Exception):
    pass


def parse(version):
    nums = [int(x) for x in re.findall(r"\d+", version or "")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def kind():
    if not getattr(sys, "frozen", False):
        return "source"
    if WIN:
        return "windows"
    if MAC:
        return "mac"
    return "linux"


def app_dir():
    return Path(sys.executable).resolve().parent


def check(current=__version__):
    try:
        page = http.final_url(f"https://github.com/{REPO}/releases/latest")
    except http.HttpError:
        return None
    found = re.search(r"/releases/tag/([\w.+-]+)$", page)
    if not found:
        return None
    tag = found.group(1)
    if parse(tag) <= parse(current):
        return None
    wanted = ASSETS.get(kind())
    url = f"https://github.com/{REPO}/releases/download/{tag}/{wanted}" if wanted else ""
    if url and kind() == "linux" and not os.access(app_dir().parent, os.W_OK):
        url = ""
    return {"version": tag.lstrip("vV"), "page": page, "url": url}


def swap(archive, target, exe_name):
    stage = target.with_name(target.name + ".new")
    old = target.with_name(target.name + ".old")
    shutil.rmtree(stage, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    stage.mkdir(parents=True)
    try:
        with tarfile.open(archive) as tf:
            tf.extractall(stage, filter="data")
        inner = list(stage.iterdir())
        src = inner[0] if len(inner) == 1 and inner[0].is_dir() else stage
        if not (src / exe_name).is_file():
            raise UpdateError("The download does not look like wowam.")
        os.rename(target, old)
        try:
            os.rename(src, target)
        except OSError:
            os.rename(old, target)
            raise
    except (OSError, tarfile.TarError) as e:
        raise UpdateError(f"Could not install the update: {e}") from e
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def cleanup():
    if kind() == "linux":
        target = app_dir()
        shutil.rmtree(target.with_name(target.name + ".old"), ignore_errors=True)
    shutil.rmtree(cache_dir() / "update", ignore_errors=True)


def install(info, progress=None, relaunch=True):
    url = info.get("url", "")
    which = kind()
    if not url or which not in ASSETS:
        raise UpdateError("This copy of wowam cannot update itself.")
    folder = cache_dir() / "update"
    shutil.rmtree(folder, ignore_errors=True)
    target = folder / ASSETS[which]
    try:
        http.download(url, target, progress=progress, timeout=120)
    except http.HttpError as e:
        raise UpdateError(f"Download failed: {e}") from e
    if which == "windows":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [str(target), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            creationflags=flags,
            close_fds=True,
        )
        return
    exe = Path(sys.executable).resolve()
    swap(target, exe.parent, exe.name)
    if relaunch:
        subprocess.Popen([str(exe)], start_new_session=True, close_fds=True)
