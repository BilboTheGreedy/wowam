import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import MAC, WIN, config_home, data_dir, data_home

APP_ID = "wowam"
BUNDLE_ID = "org.wowam.app"
AGENT_ID = "org.wowam.update"
TASK = "wowam-update"
SCHEMES = ("wago-app",)


def command(gui=False):
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = shutil.which("wowam")
    if exe:
        return [exe]
    py = sys.executable
    if WIN and gui:
        pyw = Path(py).with_name("pythonw.exe")
        if pyw.exists():
            py = str(pyw)
    launcher = Path(__file__).resolve().parents[2] / "run.py"
    if launcher.exists():
        return [py, str(launcher)]
    return [py, "-m", "wowam"]


def icon_source():
    return Path(__file__).resolve().parent / "data" / "wowam.svg"


def _run(args, env=None):
    kwargs = {}
    if WIN:
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    if env:
        kwargs["env"] = {**os.environ, **env}
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=30, **kwargs).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


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


def unit_dir():
    return config_home() / "systemd" / "user"


def _linux_install():
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


def _linux_remove():
    for path in (desktop_file(), icon_file()):
        try:
            path.unlink()
        except OSError:
            pass
    _run(["update-desktop-database", str(desktop_file().parent)])


def shortcut_file():
    return config_home() / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{APP_ID}.lnk"


def _win_icon():
    target = data_dir() / f"{APP_ID}.ico"
    try:
        from PySide6.QtGui import QGuiApplication, QIcon

        if QGuiApplication.instance() is None:
            return ""
        target.parent.mkdir(parents=True, exist_ok=True)
        if QIcon(str(icon_source())).pixmap(256, 256).save(str(target), "ICO"):
            return str(target)
    except Exception:
        pass
    return ""


def _win_install():
    import winreg

    cmd = command(gui=True)
    link = shortcut_file()
    link.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:WOWAM_LNK);"
        "$s.TargetPath=$env:WOWAM_TARGET;"
        "$s.Arguments=$env:WOWAM_ARGS;"
        "$s.Description='World of Warcraft addon manager';"
        "if($env:WOWAM_ICON){$s.IconLocation=$env:WOWAM_ICON};"
        "$s.Save()"
    )
    _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env={
            "WOWAM_LNK": str(link),
            "WOWAM_TARGET": cmd[0],
            "WOWAM_ARGS": subprocess.list2cmdline(cmd[1:]),
            "WOWAM_ICON": _win_icon(),
        },
    )
    for scheme in SCHEMES:
        base = rf"Software\Classes\{scheme}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"URL:{scheme}")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, subprocess.list2cmdline(cmd) + ' "%1"')


def _win_remove():
    import winreg

    try:
        shortcut_file().unlink()
    except OSError:
        pass
    for scheme in SCHEMES:
        base = rf"Software\Classes\{scheme}"
        for sub in (r"\shell\open\command", r"\shell\open", r"\shell", ""):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, base + sub)
            except OSError:
                pass


def bundle_dir():
    return Path.home() / "Applications" / f"{APP_ID}.app"


def _mac_install():
    bundle = bundle_dir()
    macos = bundle / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    with open(bundle / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(
            {
                "CFBundleName": APP_ID,
                "CFBundleDisplayName": APP_ID,
                "CFBundleIdentifier": BUNDLE_ID,
                "CFBundleExecutable": APP_ID,
                "CFBundlePackageType": "APPL",
                "CFBundleVersion": "1",
                "CFBundleShortVersionString": "1",
                "NSHighResolutionCapable": True,
                "CFBundleURLTypes": [{"CFBundleURLName": s, "CFBundleURLSchemes": [s]} for s in SCHEMES],
            },
            f,
        )
    script = macos / APP_ID
    script.write_text(f'#!/bin/sh\nexec {shlex.join(command())} "$@"\n')
    script.chmod(0o755)
    _run(
        [
            "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister",
            "-f",
            str(bundle),
        ]
    )


def _mac_remove():
    shutil.rmtree(bundle_dir(), ignore_errors=True)


def launcher_installed():
    if WIN:
        return shortcut_file().exists()
    if MAC:
        return bundle_dir().exists()
    return desktop_file().exists()


def install_launcher():
    if WIN:
        _win_install()
    elif MAC:
        _mac_install()
    else:
        _linux_install()


def remove_launcher():
    if WIN:
        _win_remove()
    elif MAC:
        _mac_remove()
    else:
        _linux_remove()


def agent_file():
    return Path.home() / "Library" / "LaunchAgents" / f"{AGENT_ID}.plist"


def timer_enabled():
    if WIN:
        return _run(["schtasks", "/Query", "/TN", TASK])
    if MAC:
        return agent_file().exists()
    return (unit_dir() / "timers.target.wants" / f"{APP_ID}-update.timer").exists()


def _linux_enable():
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


def _linux_disable():
    _run(["systemctl", "--user", "disable", "--now", f"{APP_ID}-update.timer"])
    for name in (f"{APP_ID}-update.timer", f"{APP_ID}-update.service"):
        try:
            (unit_dir() / name).unlink()
        except OSError:
            pass
    _run(["systemctl", "--user", "daemon-reload"])


def _mac_enable():
    path = agent_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        plistlib.dump(
            {
                "Label": AGENT_ID,
                "ProgramArguments": command() + ["auto"],
                "StartInterval": 21600,
                "RunAtLoad": True,
            },
            f,
        )
    _run(["launchctl", "unload", str(path)])
    return _run(["launchctl", "load", "-w", str(path)])


def _mac_disable():
    path = agent_file()
    _run(["launchctl", "unload", "-w", str(path)])
    try:
        path.unlink()
    except OSError:
        pass


def enable_timer():
    if WIN:
        task = subprocess.list2cmdline(command(gui=True) + ["auto"])
        return _run(["schtasks", "/Create", "/F", "/SC", "HOURLY", "/MO", "6", "/TN", TASK, "/TR", task])
    if MAC:
        return _mac_enable()
    return _linux_enable()


def disable_timer():
    if WIN:
        _run(["schtasks", "/Delete", "/F", "/TN", TASK])
    elif MAC:
        _mac_disable()
    else:
        _linux_disable()


def autostart_file():
    return config_home() / "autostart" / f"{APP_ID}.desktop"


def login_agent_file():
    return Path.home() / "Library" / "LaunchAgents" / f"{BUNDLE_ID}.plist"


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_enabled():
    if WIN:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, APP_ID)
            return True
        except OSError:
            return False
    if MAC:
        return login_agent_file().exists()
    return autostart_file().exists()


def enable_autostart():
    if WIN:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, subprocess.list2cmdline(command(gui=True)))
    elif MAC:
        path = login_agent_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            plistlib.dump({"Label": BUNDLE_ID, "ProgramArguments": command(), "RunAtLoad": True}, f)
    else:
        path = autostart_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=wowam\n"
            f"Exec={_quote(command())}\n"
            f"Icon={APP_ID}\n"
            "Terminal=false\n"
        )


def disable_autostart():
    if WIN:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, APP_ID)
        except OSError:
            pass
        return
    path = login_agent_file() if MAC else autostart_file()
    try:
        path.unlink()
    except OSError:
        pass


def notify(title, body):
    if WIN:
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$n=New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon=[System.Drawing.SystemIcons]::Information;"
            "$n.Visible=$true;"
            "$n.ShowBalloonTip(8000,$env:WOWAM_TITLE,$env:WOWAM_BODY,'Info');"
            "Start-Sleep -Seconds 9;"
            "$n.Dispose()"
        )
        _run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            env={"WOWAM_TITLE": title, "WOWAM_BODY": body},
        )
    elif MAC:
        script = (
            'display notification (system attribute "WOWAM_BODY") '
            'with title (system attribute "WOWAM_TITLE")'
        )
        _run(["osascript", "-e", script], env={"WOWAM_TITLE": title, "WOWAM_BODY": body})
    elif shutil.which("notify-send"):
        _run(["notify-send", "-a", "wowam", "-i", APP_ID, title, body])
