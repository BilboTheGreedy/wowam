import os
import re
import shutil
import subprocess
from pathlib import Path

from .paths import MAC, WIN, config_home, data_home

NAMES = ("Wow.exe", "WowClassic.exe", "WowB.exe", "WowT.exe", "WowClassicB.exe", "WowClassicT.exe")


def game_exe(client):
    for name in NAMES:
        if (client.path / name).is_file():
            return client.path / name
    for path in sorted(client.path.glob("Wow*.exe")):
        if not re.search(r"voice|error|crash", path.name, re.I):
            return path
    return None


def wine_prefix(client):
    parts = client.path.parts
    if "drive_c" not in parts:
        return None
    return Path(*parts[: parts.index("drive_c")])


def lutris_slug(prefix):
    for folder in (data_home() / "lutris" / "games", config_home() / "lutris" / "games"):
        for path in sorted(folder.glob("*.yml")) if folder.is_dir() else []:
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            found = re.search(r"^\s+prefix:\s*(.+?)\s*$", text, re.M)
            if not found or Path(found.group(1).strip("'\"")) != prefix:
                continue
            slug = re.search(r"^game_slug:\s*(\S+)", text, re.M)
            return slug.group(1) if slug else re.sub(r"-\d+$", "", path.stem)
    return ""


def plan(client):
    if MAC:
        apps = sorted(client.path.glob("*.app"))
        return (["open", str(apps[0])], {}, "Start World of Warcraft") if apps else None
    exe = game_exe(client)
    if WIN:
        return ([str(exe)], {}, "Start World of Warcraft") if exe else None
    prefix = wine_prefix(client)
    if not prefix:
        return None
    slug = lutris_slug(prefix)
    if slug and shutil.which("lutris"):
        return ["lutris", f"lutris:rungame/{slug}"], {}, "Open the game launcher through Lutris"
    found = re.search(r"compatdata/(\d+)/pfx$", prefix.as_posix())
    if found and shutil.which("steam"):
        app = int(found.group(1))
        game = app if app < 2**31 else (app << 32) | 0x02000000
        return ["steam", f"steam://rungameid/{game}"], {}, "Open the game through Steam"
    if exe and shutil.which("wine"):
        return ["wine", str(exe)], {"WINEPREFIX": str(prefix)}, "Start World of Warcraft with Wine"
    return None


def start(client):
    found = plan(client)
    if not found:
        return False
    argv, env, _ = found
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if WIN:
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        kwargs["cwd"] = str(client.path)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(argv, env={**os.environ, **env}, **kwargs)
    return True
