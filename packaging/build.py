import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"

sys.path.insert(0, str(ROOT / "src"))
from wowam import __version__

DROP = (
    "WebEngine", "Pdf", "3D", "Quick3D", "Charts", "DataVisualization", "Graphs", "Multimedia", "Location",
    "Positioning", "Sensors", "VirtualKeyboard", "Scxml", "StateMachine", "RemoteObjects", "TextToSpeech",
    "WebSockets", "WebChannel", "WebView", "Bluetooth", "Nfc", "SerialPort", "SerialBus", "Test", "Designer",
    "Help", "Sql", "Spatial", "HttpServer", "Quick3DPhysics", "QuickTimeline", "Lottie",
)


def make_icon():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication, QIcon

    app = QGuiApplication.instance() or QGuiApplication([])
    BUILD.mkdir(exist_ok=True)
    target = BUILD / "wowam.ico"
    pixmap = QIcon(str(ROOT / "src/wowam/data/wowam.svg")).pixmap(256, 256)
    if not pixmap.save(str(target), "ICO"):
        raise SystemExit("could not write icon")
    del app
    return target


def make_icns():
    sizes = {16: "16x16", 32: "16x16@2x", 64: "32x32@2x", 128: "128x128", 256: "128x128@2x", 512: "256x256@2x"}
    folder = BUILD / "wowam.iconset"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for size, name in sizes.items():
        shutil.copyfile(ROOT / f"src/wowam/data/wowam-{size}.png", folder / f"icon_{name}.png")
    shutil.copyfile(ROOT / "src/wowam/data/wowam-32.png", folder / "icon_32x32.png")
    shutil.copyfile(ROOT / "src/wowam/data/wowam-256.png", folder / "icon_256x256.png")
    target = BUILD / "wowam.icns"
    subprocess.run(["iconutil", "-c", "icns", str(folder), "-o", str(target)], check=True)
    return target


PATTERN = re.compile(r"^(lib)?Qt6?(" + "|".join(DROP) + ")")


HOST_LIBS = re.compile(
    r"^lib(stdc\+\+|gcc_s|gbm|drm|fontconfig|freetype|X|xcb(?!-cursor)|xkb|gtk|gdk|atk|atspi|cairo|pango|epoxy"
    r"|harfbuzz|wayland|EGL|GL|glapi|asound|nss|nspr|smime|plc|plds|thai|datrie|fribidi|graphite|pixman)"
)


def prune_host_libs(folder):
    removed = 0
    for path in folder.rglob("*"):
        if path.is_dir():
            continue
        top = path.parent.name == "_internal" and HOST_LIBS.match(path.name)
        if top or path.name == "libqgtk3.so":
            path.unlink()
            removed += 1
    return removed


def prune(folder):
    removed = 0
    for path in sorted(folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        inside_qt = "PySide6" in path.parts
        if not (PATTERN.match(path.name) or (inside_qt and path.name in ("translations", "resources"))):
            continue
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def size_mb(folder):
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file() and not p.is_symlink()) / 1e6


def main():
    import PyInstaller.__main__

    key = os.environ.get("CURSEFORGE_KEY", "").strip()
    if key:
        (ROOT / "src/wowam/data/cf.key").write_text(key)

    shutil.rmtree(DIST, ignore_errors=True)
    args = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", "wowam",
        "--paths", str(ROOT / "src"),
        "--add-data", f"{ROOT / 'src/wowam/gui/qml'}{os.pathsep}wowam/gui/qml",
        "--add-data", f"{ROOT / 'src/wowam/data'}{os.pathsep}wowam/data",
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
    ]
    if WIN:
        args += ["--icon", str(make_icon())]
    if MAC:
        args += ["--osx-bundle-identifier", "org.wowam.app", "--icon", str(make_icns())]
    args.append(str(ROOT / "run.py"))
    PyInstaller.__main__.run(args)

    app = DIST / ("wowam.app" if MAC else "wowam")
    before = size_mb(app)
    removed = prune(app)
    if not WIN and not MAC:
        removed += prune_host_libs(app)
    print(f"pruned {removed} items, {before:.0f} MB -> {size_mb(app):.0f} MB")
    if MAC:
        subprocess.run(["codesign", "--force", "--deep", "-s", "-", str(app)], check=True)

    if WIN:
        iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
        subprocess.run([iscc, f"/DVersion={__version__}", str(ROOT / "packaging/wowam.iss")], check=True)
    elif MAC:
        subprocess.run(
            ["ditto", "-c", "-k", "--keepParent", str(app), str(DIST / "wowam-macos.zip")], check=True
        )
    else:
        with tarfile.open(DIST / "wowam-linux-x86_64.tar.gz", "w:gz") as tf:
            tf.add(app, arcname="wowam")
    for f in sorted(DIST.iterdir()):
        if f.is_file():
            print(f"{f.name} {f.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
