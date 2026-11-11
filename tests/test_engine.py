import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import shutil
import subprocess

from wowam import auras, backup, clients, installer, launch, lists, manager, sources, toc
from wowam.sources import Release


class Cfg:
    def __init__(self, **kw):
        self.data = {"wago_key": "", "github_token": "", "backup_keep": 3}
        self.data.update(kw)

    def get(self, key):
        return self.data.get(key)


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = mock.patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "XDG_CACHE_HOME": str(self.home / "cache"),
                "XDG_DATA_HOME": str(self.home / "data"),
                "XDG_CONFIG_HOME": str(self.home / "config"),
            },
        )
        self.env.start()
        self.root = self.home / "Games/battlenet/drive_c/Program Files (x86)/World of Warcraft"
        retail = self.root / "_retail_"
        (retail / "Interface/AddOns").mkdir(parents=True)
        (retail / "WTF/Account/ACC/SavedVariables").mkdir(parents=True)
        (retail / ".flavor.info").write_text("Product Flavor!STRING:0\nwow\n")
        era = self.root / "_classic_era_"
        era.mkdir()
        (era / "WowClassic.exe").write_text("")
        (self.root / ".build.info").write_text(
            "Branch!STRING:0|Version!STRING:0|Product!STRING:0\neu|12.1.5.70783|wow\neu|1.15.8.1|wow_classic_era\n"
        )
        self.client = clients.discover(home=self.home)[0]
        self.addons = self.client.addons_dir

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def add_folder(self, name, toc_text="", extra=None):
        d = self.addons / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.toc").write_text(toc_text)
        for k, v in (extra or {}).items():
            (d / k).write_text(v)
        return d


class ClientTests(Base):
    def test_discover(self):
        found = clients.discover(home=self.home)
        self.assertEqual([c.folder for c in found], ["_retail_", "_classic_era_"])
        self.assertEqual(found[0].flavor, "mainline")
        self.assertEqual(found[0].version, "12.1.5.70783")
        self.assertEqual(found[0].interface, 120105)
        self.assertEqual(found[1].flavor, "classic")
        self.assertEqual(found[0].location, "battlenet")

    def test_extra_path(self):
        other = self.home / "elsewhere/World of Warcraft/_retail_"
        other.mkdir(parents=True)
        (other / "Wow.exe").write_text("")
        found = clients.discover([str(other)], home=self.home)
        self.assertEqual(len(found), 3)

    def test_flavors(self):
        self.assertEqual(clients.flavor_for("wowf", "_forever_", "1.60.1.1"), "forever")
        self.assertEqual(clients.flavor_for("wow_classic", "_classic_", "5.5.4.1"), "mists")
        self.assertEqual(clients.flavor_for("wow_classic_beta", "_classic_beta_", ""), "mists")
        self.assertEqual(clients.flavor_of_version("1.60.1"), "forever")
        self.assertEqual(clients.flavor_of_version("1.15.9"), "classic")
        self.assertEqual(clients.flavor_of_version("12.1.5"), "mainline")


class TocTests(Base):
    def test_parse_and_pick(self):
        d = self.add_folder("Foo", "## Interface: 11508\n## Title: |cff00ff00Foo|r Bar\n## Version: 1.0\n")
        (d / "Foo_Mainline.toc").write_text("## Interface: 120105\n## Version: 2.0\n## Dependencies: A, B\n")
        fields = toc.read(d, "mainline")
        self.assertEqual(fields["version"], "2.0")
        self.assertEqual(toc.deps(fields), ["A", "B"])
        self.assertEqual(toc.read(d, "classic")["version"], "1.0")
        self.assertEqual(toc.clean("|cff00ff00Foo|r Bar"), "Foo Bar")
        self.assertEqual(toc.strip_suffix("Foo_Mainline"), "Foo")


class RefTests(unittest.TestCase):
    def test_parse(self):
        cases = {
            "gh:a/b": "gh:a/b",
            "https://github.com/BigWigsMods/BigWigs/releases": "gh:BigWigsMods/BigWigs",
            "https://github.com/a/b.git": "gh:a/b",
            "https://www.wowinterface.com/downloads/info24910-WeakAuras2.html": "wowi:24910",
            "wowi:5086": "wowi:5086",
            "https://addons.wago.io/addons/plater": "wago:plater",
            "wago-app://addons/kRNLep6o": "wago:kRNLep6o",
            "wa:details": "wago:details",
            "ElvUI": "tukui:elvui",
            "https://tukui.org/elvui": "tukui:elvui",
            "a/b": "gh:a/b",
        }
        for text, want in cases.items():
            self.assertEqual(sources.parse_ref(text), want, text)
        for bad in ("", "hello", "wowi:abc", "gh:nope", "https://example.com/x"):
            self.assertIsNone(sources.parse_ref(bad), bad)

    def test_same_version(self):
        self.assertTrue(manager.same_version("v1.2", "1.2"))
        self.assertTrue(manager.same_version("5.5.3 (v202609120600)", "v202609120600"))
        self.assertFalse(manager.same_version("1.2", "1.2.1"))
        self.assertFalse(manager.same_version("", ""))

    def test_github_pick(self):
        client = mock.Mock(flavor="classic", label="Classic Era")
        release = {
            "assets": [
                {"name": "Foo-1.0.zip", "browser_download_url": "u/retail"},
                {"name": "Foo-1.0-classic.zip", "browser_download_url": "u/classic"},
                {"name": "Foo-1.0-nolib.zip", "browser_download_url": "u/nolib"},
            ]
        }
        self.assertEqual(sources._gh_pick(release, client), "u/classic")
        client.flavor = "mainline"
        self.assertEqual(sources._gh_pick(release, client), "u/retail")
        release["assets"].append({"name": "release.json", "browser_download_url": "u/json"})
        manifest = {
            "releases": [
                {"filename": "Foo-1.0-nolib.zip", "nolib": True, "metadata": [{"flavor": "mainline"}]},
                {"filename": "Foo-1.0.zip", "nolib": False, "metadata": [{"flavor": "mainline"}]},
            ]
        }
        with mock.patch.object(sources.http, "get_json", return_value=manifest):
            self.assertEqual(sources._gh_pick(release, client), "u/retail")
            client.flavor = "cata"
            self.assertIsNone(sources._gh_pick(release, client))


class InstallerTests(Base):
    def test_plain_zip(self):
        z = make_zip(self.home / "a.zip", {"Foo/Foo.toc": "x", "Foo/a.lua": "1", "Foo_Opt/Foo_Opt.toc": "y"})
        self.assertEqual(installer.install_zip(z, self.addons), ["Foo", "Foo_Opt"])
        self.assertTrue((self.addons / "Foo/a.lua").exists())
        self.assertEqual([p.name for p in self.addons.iterdir() if p.name.startswith(".")], [])

    def test_zipball_and_root(self):
        z = make_zip(self.home / "b.zip", {"me-Foo-abc123/Foo.toc": "x", "me-Foo-abc123/Foo_Mainline.toc": "x"})
        self.assertEqual(installer.install_zip(z, self.addons), ["Foo"])
        z = make_zip(self.home / "c.zip", {"Bar.toc": "x", "core.lua": "1"})
        self.assertEqual(installer.install_zip(z, self.addons), ["Bar"])
        self.assertTrue((self.addons / "Bar/core.lua").exists())

    def test_unsafe_and_empty(self):
        z = make_zip(self.home / "d.zip", {"../evil.toc": "x"})
        with self.assertRaises(installer.InstallError):
            installer.install_zip(z, self.addons)
        self.assertFalse((self.home / "evil.toc").exists())
        z = make_zip(self.home / "e.zip", {"readme.txt": "x"})
        with self.assertRaises(installer.InstallError):
            installer.install_zip(z, self.addons)

    def test_replaces_old(self):
        self.add_folder("Foo", "old", {"stale.lua": "1"})
        z = make_zip(self.home / "f.zip", {"Foo/Foo.toc": "new"})
        installer.install_zip(z, self.addons)
        self.assertFalse((self.addons / "Foo/stale.lua").exists())


class ManagerTests(Base):
    def setUp(self):
        super().setUp()
        self.cfg = Cfg()
        self.mgr = manager.Manager(self.client, self.cfg)
        self.version = "2.0"
        self.files = {"Foo/Foo.toc": "## Title: Foo\n## Version: 2.0\n", "Foo_Opt/Foo_Opt.toc": "## Version: 2.0\n"}

        def fake_latest(ref, client, cfg, channel="stable"):
            if ref == "gh:bad/repo":
                raise sources.SourceError("nope")
            return Release(version=self.version, url="zip://", author="me")

        def fake_download(url, dest, headers=None, progress=None, timeout=60):
            dest.parent.mkdir(parents=True, exist_ok=True)
            make_zip(dest, self.files)
            return dest

        self.patches = [
            mock.patch.object(sources, "latest", fake_latest),
            mock.patch.object(manager.http, "download", fake_download),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        super().tearDown()

    def test_install_update_remove(self):
        rec = self.mgr.install("gh:me/foo")
        self.assertEqual(rec["dirs"], ["Foo", "Foo_Opt"])
        self.assertEqual(rec["name"], "Foo")
        addon = self.mgr.list()[0]
        self.assertTrue(addon.managed)
        self.assertFalse(addon.modified)
        self.assertFalse(manager.needs_update(addon, self.mgr.latest(addon)))

        self.version = "3.0"
        self.files = {"Foo/Foo.toc": "## Title: Foo\n## Version: 3.0\n"}
        result = manager.survey(self.mgr)
        self.assertTrue(manager.can_auto_update(result[0][0], result[0][1]))
        self.mgr.apply("gh:me/foo", result[0][1])
        self.assertFalse((self.addons / "Foo_Opt").exists())
        self.assertEqual(self.mgr.list()[0].version, "3.0")

        (self.addons / "Foo/Foo.toc").write_text("edited")
        addon = self.mgr.list()[0]
        self.assertTrue(addon.modified)
        self.version = "4.0"
        self.assertFalse(manager.can_auto_update(addon, self.mgr.latest(addon)))

        self.mgr.uninstall(addon)
        self.assertEqual(self.mgr.list(), [])
        self.assertFalse((self.addons / "Foo").exists())

    def test_rollback_and_history(self):
        from wowam import history

        self.mgr.install("gh:me/foo")
        self.assertEqual(self.mgr.list()[0].previous, "")
        self.version = "3.0"
        self.files = {"Foo/Foo.toc": "## Title: Foo\n## Version: 3.0\n"}
        self.mgr.install("gh:me/foo")
        addon = self.mgr.list()[0]
        self.assertEqual(addon.previous, "2.0")
        rec = self.mgr.rollback("gh:me/foo")
        self.assertEqual(rec["version"], "2.0")
        addon = self.mgr.list()[0]
        self.assertTrue(addon.pinned)
        self.assertFalse(addon.modified)
        self.assertEqual(addon.previous, "")
        self.assertTrue((self.addons / "Foo_Opt").exists())
        self.assertIn("Version: 2.0", (self.addons / "Foo/Foo.toc").read_text())
        self.assertEqual([(h["old"], h["new"]) for h in history.entries()], [("3.0", "2.0"), ("2.0", "3.0"), ("", "2.0")])
        with self.assertRaises(sources.SourceError):
            self.mgr.rollback("gh:me/foo")

    def test_health(self):
        self.add_folder("Old", "## Interface: 110207\n## Dependencies: Ace3, Blizzard_Foo\n")
        self.add_folder("New", "## Interface: 120105, 11508\n## RequiredDeps: Old\n")
        found = {a.name: a for a in self.mgr.list()}
        self.assertTrue(found["Old"].outdated)
        self.assertEqual(found["Old"].needs, ["Ace3"])
        self.assertFalse(found["New"].outdated)
        self.assertEqual(found["New"].needs, [])

    def test_grouping_and_adopt(self):
        self.add_folder("BugSack", "## Title: BugSack\n## Version: v1\n## X-Website: https://github.com/funkydude/BugSack\n")
        self.add_folder("Thing", "## Title: Thing\n## Version: 1\n## X-Wago-ID: abc\n")
        self.add_folder("Thing_Options", "## Dependencies: Thing\n")
        self.add_folder("ThingExtra", "## Version: 1\n")
        self.add_folder("Other", "## X-Website: https://github.com/bad/repo\n## X-WoWI-ID: 77\n")
        (self.addons / "Blizzard_X").mkdir()
        listed = {a.key: a for a in self.mgr.list()}
        self.assertEqual(sorted(listed), ["local:BugSack", "local:Other", "local:Thing"])
        self.assertEqual(listed["local:Thing"].dirs, ["Thing", "ThingExtra", "Thing_Options"])
        self.assertEqual(listed["local:Thing"].candidates, [])
        self.assertTrue(listed["local:Thing"].note)
        self.assertEqual(listed["local:BugSack"].candidates, ["gh:funkydude/BugSack"])
        self.assertEqual(listed["local:Other"].candidates, ["gh:bad/repo", "wowi:77"])

        result = {a.key: (a, r) for a, r, e in manager.survey(self.mgr)}
        self.assertIn("gh:funkydude/BugSack", result)
        self.assertIn("wowi:77", result)
        self.assertIn("local:Thing", result)
        adopted = result["gh:funkydude/BugSack"][0]
        self.assertTrue(manager.needs_update(adopted, result["gh:funkydude/BugSack"][1]))
        self.assertEqual(self.mgr.refs(), ["gh:funkydude/BugSack", "wowi:77"])

    def test_adopted_update_keeps_unlisted_dirs(self):
        self.add_folder("Foo", "## Version: 1\n## X-WoWI-ID: 5\n")
        self.add_folder("Foo_Third", "## Version: 9\n")
        manager.survey(self.mgr)
        self.files = {"Foo/Foo.toc": "## Version: 2.0\n"}
        self.mgr.install("wowi:5")
        self.assertTrue((self.addons / "Foo_Third").exists())
        keys = sorted(a.key for a in self.mgr.list())
        self.assertEqual(keys, ["local:Foo_Third", "wowi:5"])

    def test_pin_and_orphans(self):
        self.mgr.install("gh:me/foo")
        self.mgr.set_field("gh:me/foo", "pinned", True)
        self.version = "9"
        addon = self.mgr.list()[0]
        self.assertTrue(addon.pinned)
        self.assertFalse(manager.can_auto_update(addon, self.mgr.latest(addon)))
        sv = self.client.wtf_dir / "Account/ACC/SavedVariables"
        (sv / "Foo.lua").write_text("x")
        (sv / "Gone.lua").write_text("x")
        (sv / "Gone.lua.bak").write_text("x")
        (sv / "Blizzard_Thing.lua").write_text("x")
        self.assertEqual({o["addon"] for o in self.mgr.orphans()}, {"Gone"})
        self.assertEqual(self.mgr.clean_orphans(), 2)
        self.assertTrue((sv / "Foo.lua").exists())
        self.assertTrue((sv / "Blizzard_Thing.lua").exists())

    def test_backup_restore(self):
        sv = self.client.wtf_dir / "Account/ACC/SavedVariables"
        (sv / "Foo.lua").write_text("one")
        self.mgr.install("gh:me/foo")
        first = backup.create(self.client, 3)
        self.assertTrue(first.exists())
        (sv / "Foo.lua").write_text("two")
        backup.restore(self.client, first.name)
        self.assertEqual((sv / "Foo.lua").read_text(), "one")
        self.assertEqual(self.mgr.refs(), ["gh:me/foo"])

    def test_parse_refs(self):
        self.assertEqual(manager.parse_refs("gh:a/b, wowi:5\nelvui junk"), ["gh:a/b", "wowi:5", "tukui:elvui"])


if __name__ == "__main__":
    unittest.main()


class ExtraTests(Base):
    def test_curseforge(self):
        self.assertEqual(sources.parse_ref("https://www.curseforge.com/wow/addons/Deadly-Boss-Mods/files"), "cf:deadly-boss-mods")
        self.assertEqual(sources.parse_ref("curse:3358"), "cf:3358")
        self.assertEqual(sources.label("cf:3358"), "CurseForge")
        with self.assertRaises(sources.SourceError):
            sources.latest("cf:3358", self.client, Cfg())
        seen = []

        def fake(url, headers=None, etag=False, max_age=0, timeout=30):
            seen.append(url)
            self.assertEqual(headers["x-api-key"], "k")
            if "/files" in url:
                return {
                    "data": [
                        {"displayName": "old", "fileDate": "2026-01-01", "releaseType": 1, "downloadUrl": "u1"},
                        {"displayName": "beta", "fileDate": "2026-03-01", "releaseType": 2, "downloadUrl": "u3"},
                        {"displayName": "new", "fileDate": "2026-02-01", "releaseType": 1, "downloadUrl": "u2"},
                    ]
                }
            if "slug=" in url:
                return {"data": [{"id": 7, "name": "Thing", "authors": [{"name": "me"}], "links": {"websiteUrl": "w"}}]}
            return {"data": {"id": 7, "name": "Thing", "authors": [{"name": "me"}], "links": {"websiteUrl": "w"}}}

        cfg = Cfg(curseforge_key="k")
        with mock.patch.object(sources.http, "get_json", fake):
            rel = sources.latest("cf:thing", self.client, cfg)
            self.assertEqual((rel.version, rel.url, rel.name, rel.author), ("new", "u2", "Thing", "me"))
            self.assertIn("gameVersionTypeId=517", seen[-1])
            self.assertEqual(sources.latest("cf:7", self.client, cfg, "beta").version, "beta")

    def test_auras(self):
        self.assertEqual(auras.sync(self.client), [])
        self.add_folder("WeakAuras", "## Title: WeakAuras\n")
        saved = self.client.wtf_dir / "Account/ACC/SavedVariables/WeakAuras.lua"
        saved.write_text(
            'WeakAurasSaved = {\n["displays"] = {\n["A"] = {\n["url"] = "https://wago.io/abc/3",\n},\n'
            '["B"] = {\n["url"] = "https://wago.io/abc/2",\n},\n["C"] = {\n["url"] = "https://wago.io/Named",\n},\n'
            '["D"] = {\n["url"] = "",\n},\n}\n}\n'
        )
        self.assertEqual(auras.local(self.client), {"abc": 2, "Named": 1})
        reply = [
            {"_id": "abc", "slug": "pretty", "name": "One ]=] two", "username": "me", "version": 5, "versionString": "1.0.4", "changelog": {"text": "x"}},
            {"_id": "zzz", "slug": "Named", "name": "Same", "username": "me", "version": 1, "versionString": "1.0.0", "changelog": {}},
        ]

        def fake_download(url, dest, headers=None, progress=None, timeout=60):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("!WA:2!abc")
            return dest

        with mock.patch.object(auras.http, "get_json", return_value=reply), mock.patch.object(auras.http, "download", fake_download):
            found = auras.sync(self.client)
        self.assertEqual(found, [{"name": "One ]=] two", "old": 2, "new": 5}])
        folder = self.addons / auras.FOLDER
        data = (folder / "Data.lua").read_text()
        self.assertIn('[=[abc]=]', data)
        self.assertIn("[==[One ]=] two]==]", data)
        self.assertNotIn(auras.FOLDER, [a.name for a in manager.Manager(self.client, Cfg()).list()])
        if shutil.which("luac"):
            for name in ("Data.lua", "Init.lua"):
                self.assertEqual(subprocess.run(["luac", "-p", str(folder / name)]).returncode, 0)
        with mock.patch.object(auras.http, "get_json", return_value=[]):
            self.assertEqual(auras.sync(self.client), [])
        self.assertNotIn("abc", (folder / "Data.lua").read_text())

    @unittest.skipIf(sys.platform in ("win32", "darwin"), "wine only")
    def test_launch(self):
        self.assertEqual(launch.wine_prefix(self.client), self.home / "Games/battlenet")
        games = self.home / "data/lutris/games"
        games.mkdir(parents=True)
        (games / "battlenet-1.yml").write_text(f"game:\n  exe: x\n  prefix: {self.home}/Games/battlenet\ngame_slug: battlenet\n")
        with mock.patch.object(launch.shutil, "which", lambda name: "/usr/bin/" + name if name == "lutris" else None):
            self.assertEqual(launch.plan(self.client)[0], ["lutris", "lutris:rungame/battlenet"])
        with mock.patch.object(launch.shutil, "which", lambda name: None):
            self.assertIsNone(launch.plan(self.client))


class ListTests(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(
            lists.list_url("https://github.com/a/b/blob/main/lists/x.txt"),
            "https://raw.githubusercontent.com/a/b/main/lists/x.txt",
        )
        self.assertEqual(
            lists.list_url("https://gist.github.com/someone/0123abcd"),
            "https://gist.githubusercontent.com/someone/0123abcd/raw",
        )
        self.assertEqual(lists.list_url("https://example.com/my.txt"), "https://example.com/my.txt")
        self.assertIsNone(lists.list_url("https://github.com/BigWigsMods/BigWigs"))
        self.assertIsNone(lists.list_url("https://github.com/a/b/blob/main/README.md"))
        self.assertIsNone(lists.list_url("gh:a/b wowi:1"))
        self.assertIsNone(lists.list_url("http://example.com/my.txt"))

    def test_parse(self):
        item = lists.parse("# name: Healer\n# by: me\n# for: Retail\n# note\ngh:a/b\nwowi:5, gh:a/b\n", "healer")
        self.assertEqual(item["name"], "Healer")
        self.assertEqual(item["by"], "me")
        self.assertEqual(item["game"], "Retail")
        self.assertEqual(item["refs"], ["gh:a/b", "wowi:5"])
        self.assertEqual(lists.parse("gh:a/b", "my-list")["name"], "my list")

    def test_fetch(self):
        with mock.patch.object(lists.http, "get_bytes", return_value=b"# name: X\ngh:a/b\n"):
            self.assertEqual(lists.fetch("https://example.com/x.txt")["refs"], ["gh:a/b"])
        with mock.patch.object(lists.http, "get_bytes", return_value=b"hello"):
            with self.assertRaises(sources.SourceError):
                lists.fetch("https://example.com/x.txt")

    def test_unpack(self):
        import io
        import tarfile

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for name, text in {
                "repo-main/lists/b.txt": "# name: Beta\ngh:a/b\n",
                "repo-main/lists/a.txt": "# name: Alpha\nwowi:1 wowi:2\n",
                "repo-main/lists/empty.txt": "nothing\n",
                "repo-main/README.md": "gh:x/y\n",
                "repo-main/lists/sub/c.txt": "gh:x/y\n",
            }.items():
                data = text.encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        found = lists.unpack(buf.getvalue())
        self.assertEqual([i["name"] for i in found], ["Alpha", "Beta"])
        self.assertEqual(found[0]["refs"], ["wowi:1", "wowi:2"])

    def test_share(self):
        text = lists.template(["gh:a/b"], "Retail")
        self.assertEqual(lists.parse(text)["refs"], ["gh:a/b"])
        self.assertIn("value=", lists.share_url(text))
        self.assertNotIn("value=", lists.share_url("x" * 7000))


class BranchTests(unittest.TestCase):
    def test_no_releases(self):
        commit = {"sha": "abcdef1234567890", "commit": {"message": "fix", "committer": {"date": "2026-10-02T19:44:06Z"}}}

        def fake(url, *a, **kw):
            return [] if "/releases" in url else [commit]

        with mock.patch.object(sources.http, "get_json", fake):
            rel = sources._gh_latest("a/b", None, Cfg(), "stable")
        self.assertEqual(rel.version, "2026-10-02-abcdef1")
        self.assertEqual(rel.url, "https://api.github.com/repos/a/b/zipball/abcdef1234567890")
        self.assertEqual(rel.notes, "fix")
