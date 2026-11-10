import shutil
import subprocess
import sys
from pathlib import Path

from .paths import config_home, data_home

APP_ID = "wowam"
SCHEMES = ("wago-app",)


def command():
    exe = shutil.which("wowam")
    if exe:
        return [exe]
    src = Path(__file__).resolve().parent.parent
    return ["/usr/bin/env", f"PYTHONPATH={src}", sys.executable, "-m", "wowam"]


def _quote(args):
    out = []
    for a in args:
        a = a.replace("\\", "\\\\").replace('"', '\\"')
        out.append(f'"{a}"' if " " in a or '"' in a else a)
    return " ".join(out)


def desktop_file():
    return data_home() / "applications" / f"{APP_ID}.desktop"


def icon_file():
    return data_home() / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"


def icon_source():
    return Path(__file__).resolve().parent / "data" / "wowam.svg"


def unit_dir():
    return config_home() / "systemd" / "user"


def _run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def launcher_installed():
    return desktop_file().exists()


def install_launcher():
    icon = icon_file()
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(icon_source(), icon)
    entry = desktop_file()
    entry.parent.mkdir(parents=True, exist_ok=True)
    mime = "".join(f"x-scheme-handler/{s};" for s in SCHEMES)
    entry.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=wowam\n"
        "GenericName=WoW Addon Manager\n"
        "Comment=Install and update World of Warcraft addons\n"
        f"Exec={_quote(command())} %u\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "Categories=Game;\n"
        f"StartupWMClass={APP_ID}\n"
        f"MimeType={mime}\n"
    )
    _run(["update-desktop-database", str(entry.parent)])
    for scheme in SCHEMES:
        _run(["xdg-mime", "default", entry.name, f"x-scheme-handler/{scheme}"])


def remove_launcher():
    for path in (desktop_file(), icon_file()):
        try:
            path.unlink()
        except OSError:
            pass
    _run(["update-desktop-database", str(desktop_file().parent)])


def timer_enabled():
    return (unit_dir() / "timers.target.wants" / f"{APP_ID}-update.timer").exists()


def enable_timer():
    units = unit_dir()
    units.mkdir(parents=True, exist_ok=True)
    (units / f"{APP_ID}-update.service").write_text(
        "[Unit]\n"
        "Description=Update World of Warcraft addons\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={_quote(command() + ['auto'])}\n"
    )
    (units / f"{APP_ID}-update.timer").write_text(
        "[Unit]\n"
        "Description=Update World of Warcraft addons regularly\n\n"
        "[Timer]\n"
        "OnStartupSec=3min\n"
        "OnUnitActiveSec=6h\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    _run(["systemctl", "--user", "daemon-reload"])
    return _run(["systemctl", "--user", "enable", "--now", f"{APP_ID}-update.timer"])


def disable_timer():
    _run(["systemctl", "--user", "disable", "--now", f"{APP_ID}-update.timer"])
    for name in (f"{APP_ID}-update.timer", f"{APP_ID}-update.service"):
        try:
            (unit_dir() / name).unlink()
        except OSError:
            pass
    _run(["systemctl", "--user", "daemon-reload"])


def notify(title, body):
    if shutil.which("notify-send"):
        _run(["notify-send", "-a", "wowam", "-i", APP_ID, title, body])
