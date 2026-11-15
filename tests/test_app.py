import io
import os
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wowam import selfupdate, sources

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
except ImportError:
    QGuiApplication = None


def add_file(tf, name, text):
    data = text.encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o755
    tf.addfile(info, io.BytesIO(data))


class SelfUpdateTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(selfupdate.parse("v1.2.3"), (1, 2, 3))
        self.assertEqual(selfupdate.parse("0.2"), (0, 2, 0))
        self.assertGreater(selfupdate.parse("v0.10.0"), selfupdate.parse("0.9.9"))

    def test_check(self):
        repo = selfupdate.REPO
        page = f"https://github.com/{repo}/releases/tag/v9.0.0"
        with mock.patch.object(selfupdate.http, "final_url", return_value=page):
            info = selfupdate.check("0.1.0")
            self.assertEqual(info["version"], "9.0.0")
            self.assertEqual(info["url"], "")
            self.assertEqual(info["page"], page)
            self.assertIsNone(selfupdate.check("9.0.0"))
            self.assertIsNone(selfupdate.check("9.0.1"))
            with mock.patch.object(selfupdate, "kind", return_value="windows"):
                want = f"https://github.com/{repo}/releases/download/v9.0.0/wowam-setup.exe"
                self.assertEqual(selfupdate.check("0.1.0")["url"], want)
        with mock.patch.object(selfupdate.http, "final_url", return_value=f"https://github.com/{repo}/releases"):
            self.assertIsNone(selfupdate.check("0.1.0"))

    def test_swap(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            app = tmp / "wowam-app"
            app.mkdir()
            (app / "wowam").write_text("old")
            (app / "stale").write_text("x")
            good = tmp / "good.tar.gz"
            with tarfile.open(good, "w:gz") as tf:
                add_file(tf, "wowam/wowam", "new")
                add_file(tf, "wowam/_internal/lib", "x")
            selfupdate.swap(good, app, "wowam")
            self.assertEqual((app / "wowam").read_text(), "new")
            self.assertFalse((app / "stale").exists())
            self.assertTrue((tmp / "wowam-app.old" / "stale").exists())
            self.assertFalse((tmp / "wowam-app.new").exists())

            bad = tmp / "bad.tar.gz"
            with tarfile.open(bad, "w:gz") as tf:
                add_file(tf, "other/readme", "x")
            with self.assertRaises(selfupdate.UpdateError):
                selfupdate.swap(bad, app, "wowam")
            self.assertEqual((app / "wowam").read_text(), "new")


@unittest.skipIf(QGuiApplication is None, "PySide6 not installed")
class PlainTextTests(unittest.TestCase):
    def test_every_text_has_a_format(self):
        root = Path(__file__).resolve().parent.parent / "src" / "wowam" / "gui" / "qml" / "Wowam"
        bad = []
        for path in sorted(root.glob("*.qml")):
            lines = path.read_text().split("\n")
            for i, line in enumerate(lines):
                if "Text {" not in line:
                    continue
                block = [line]
                depth = line.count("{") - line.count("}")
                j = i + 1
                while depth > 0 and j < len(lines):
                    block.append(lines[j])
                    depth += lines[j].count("{") - lines[j].count("}")
                    j += 1
                if not any("textFormat" in b for b in block):
                    bad.append(f"{path.name}:{i + 1}")
        self.assertEqual(bad, [])

    @unittest.skipIf(QGuiApplication is None, "no PySide6")
    def test_notes_lose_images(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from wowam.gui import app as gui

        out = gui.no_images('a ![x](http://h/t.png) b <img src="http://h/t.png"> c')
        self.assertNotIn("http://", out)
        with mock.patch.object(gui.http, "get_bytes", side_effect=gui.http.HttpError(0, "no")):
            self.assertNotIn("http://", gui.local_images("![x](http://h/t.png)", ""))


@unittest.skipIf(QGuiApplication is None, "no PySide6")
class DoorTests(unittest.TestCase):
    def test_second_start_hands_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp, "APPDATA": tmp, "HOME": tmp}):
                os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
                from wowam.gui import app as gui

                qapp = QGuiApplication.instance() or QGuiApplication([])
                self.assertFalse(gui.hand_over("gh:a/b"))
                door = gui.Door(qapp)
                got = []
                door.opened.connect(got.append)
                self.assertTrue(gui.hand_over("gh:a/b"))
                end = time.time() + 3
                while not got and time.time() < end:
                    qapp.processEvents()
                    time.sleep(0.01)
                door.server.close()
                self.assertEqual(got, ["gh:a/b"])


class WindowTests(unittest.TestCase):
    def test_window_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "XDG_CONFIG_HOME": str(home / "config"),
                "XDG_DATA_HOME": str(home / "data"),
                "XDG_CACHE_HOME": str(home / "cache"),
                "WOWAM_THEME": "dark",
            }
            client = home / "wow" / "_retail_"
            addon = client / "Interface" / "AddOns" / "Foo"
            addon.mkdir(parents=True)
            (addon / "Foo.toc").write_text("## Title: Foo\n## Version: 1\n")
            (client / ".flavor.info").write_text("Product Flavor!STRING:0\nwow\n")
            with mock.patch.dict(os.environ, env):
                os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
                os.environ.setdefault("QT_QUICK_BACKEND", "software")
                os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
                from wowam.gui import app as gui

                qapp = QGuiApplication.instance() or QGuiApplication([])
                update = {"version": "9.9.9", "page": "p", "url": ""}
                with mock.patch.object(sources, "wowi_by_dir", return_value=[]), mock.patch.object(
                    gui.selfupdate, "check", return_value=update
                ):
                    backend = gui.Backend("")
                    backend.cfg.set("extra_paths", [str(home / "wow")])
                    engine = QQmlApplicationEngine()
                    problems = []
                    engine.warnings.connect(lambda ws: problems.extend(w.toString() for w in ws))
                    engine.addImportPath(str(gui.QML_DIR))
                    engine.rootContext().setContextProperty("backend", backend)
                    engine.load(QUrl.fromLocalFile(str(gui.QML_DIR / "Wowam" / "Main.qml")))
                    self.assertTrue(engine.rootObjects(), problems)
                    window = engine.rootObjects()[0]
                    backend.start()
                    self.spin(qapp, lambda: backend.addonCount == 1 and not backend.checking and backend.updateVersion)
                    self.assertEqual(backend.addonCount, 1)
                    self.assertEqual(backend.updateVersion, "9.9.9")
                    rows = backend.addons.rows()
                    self.assertEqual(rows[0]["name"], "Foo")
                    self.assertEqual(rows[0]["status"], "unknown")
                    shown = []
                    backend.listReady.connect(shown.append)
                    backend._shared = [
                        {"slug": "s", "name": "Setup", "by": "me", "game": "Retail", "about": "", "refs": ["gh:a/b"]}
                    ]
                    backend._shared_at = time.time()
                    backend.sharedChanged.emit()
                    self.assertEqual(backend.sharedLists[0]["count"], 1)
                    backend.openShared("s")
                    self.spin(qapp, lambda: False, 0.3)
                    self.assertEqual(shown[0]["count"], 1)
                    self.assertEqual(shown[0]["missing"], "gh:a/b")
                    asked = []
                    backend.shareRequested.connect(asked.append)
                    backend.openShare()
                    self.spin(qapp, lambda: False, 0.3)
                    self.assertEqual(asked, [])
                    self.assertTrue(backend.welcomeNeeded)
                    window.show()
                    self.spin(qapp, lambda: False, 0.3)
                    backend.setWelcomed()
                    self.assertFalse(backend.welcomeNeeded)
                    window.setProperty("settingsOpen", True)
                    self.spin(qapp, lambda: False, 0.5)
                    found = list(problems)
                    engine.warnings.disconnect()
                    backend.shutdown()
                    del window
                    del engine
                    self.assertEqual(found, [])

    def spin(self, qapp, ready, seconds=15):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            qapp.processEvents()
            if ready():
                return
            time.sleep(0.02)


if __name__ == "__main__":
    unittest.main()
