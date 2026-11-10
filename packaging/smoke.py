import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"


def launch(exe, label):
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.txt"
        env = dict(os.environ)
        env.update(
            {
                "WOWAM_SMOKE": str(report),
                "XDG_CONFIG_HOME": str(Path(tmp) / "config"),
                "XDG_DATA_HOME": str(Path(tmp) / "data"),
                "XDG_CACHE_HOME": str(Path(tmp) / "cache"),
                "QT_QUICK_BACKEND": "software",
            }
        )
        if not WIN and not MAC:
            env["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run([str(exe)], env=env, timeout=180)
        text = report.read_text() if report.exists() else "no report written"
        print(f"{label}: exit {result.returncode}, report: {text}")
        if result.returncode != 0 or text != "ok":
            raise SystemExit(1)


def main():
    if MAC:
        launch(DIST / "wowam.app/Contents/MacOS/wowam", "bundle")
    elif WIN:
        launch(DIST / "wowam/wowam.exe", "bundle")
        setup = DIST / "wowam-setup.exe"
        subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True, timeout=600)
        subprocess.run(["taskkill", "/IM", "wowam.exe", "/F"], capture_output=True)
        installed = Path(os.environ["LOCALAPPDATA"]) / "Programs/wowam/wowam.exe"
        if not installed.exists():
            raise SystemExit("installer did not install wowam.exe")
        launch(installed, "installed")
    else:
        launch(DIST / "wowam/wowam", "bundle")
        result = subprocess.run([str(DIST / "wowam/wowam"), "--version"], capture_output=True, text=True, timeout=60)
        print("version:", result.stdout.strip())
        if result.returncode != 0 or not result.stdout.strip():
            raise SystemExit(1)


if __name__ == "__main__":
    main()
