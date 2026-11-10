import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import Property, QAbstractListModel, QModelIndex, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from .. import __version__, backup, desktop, sources
from ..clients import discover
from ..config import Config
from ..manager import Manager, can_auto_update, check_one, needs_update, parse_refs, survey
from ..sources import SourceError

QML_DIR = Path(__file__).resolve().parent / "qml"

ADDON_ROLES = [
    "key", "name", "version", "latest", "source", "status", "statusText", "pinned", "modified", "managed",
    "progress", "author", "page", "channel", "action", "folders", "busy",
]
CLIENT_ROLES = ["key", "label", "location", "version", "updates"]
BROWSE_ROLES = [
    "key", "name", "author", "version", "source", "summary", "compatible", "page", "installed", "busy", "progress",
]


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


class ListModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, roles, parent=None):
        super().__init__(parent)
        self._roles = roles
        self._rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        i = role - Qt.UserRole - 1
        if 0 <= i < len(self._roles):
            return self._rows[index.row()].get(self._roles[i])
        return None

    def roleNames(self):
        return {Qt.UserRole + 1 + i: name.encode() for i, name in enumerate(self._roles)}

    @Property(int, notify=countChanged)
    def count(self):
        return len(self._rows)

    def sync(self, rows):
        if [r["key"] for r in rows] == [r["key"] for r in self._rows]:
            for i, row in enumerate(rows):
                if row != self._rows[i]:
                    self._rows[i] = row
                    idx = self.index(i, 0)
                    self.dataChanged.emit(idx, idx)
            return
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()
        self.countChanged.emit()

    def patch(self, key, **changes):
        for i, row in enumerate(self._rows):
            if row["key"] == key:
                row.update(changes)
                idx = self.index(i, 0)
                self.dataChanged.emit(idx, idx)
                return True
        return False

    def rows(self):
        return self._rows


class Entry:
    def __init__(self, addon, checking=False):
        self.addon = addon
        self.release = None
        self.error = ""
        self.checking = checking
        self.busy = ""
        self.progress = 0.0
        self.guess = ""
        self.guess_name = ""
        self.guess_dirs = []


class Backend(QObject):
    _post = Signal(object)
    toast = Signal(str, bool)
    changed = Signal()
    settingsChanged = Signal()
    backupsChanged = Signal()
    orphansChanged = Signal()
    browseChanged = Signal()
    showBrowse = Signal(str)

    def __init__(self, uri=""):
        super().__init__()
        self._uri = uri
        self.cfg = Config()
        self._pool = ThreadPoolExecutor(max_workers=6)
        self._post.connect(self._run, Qt.QueuedConnection)
        self._clients = []
        self._managers = {}
        self._index = -1
        self._gen = 0
        self._entries = {}
        self._filter = ""
        self._loading = False
        self._searching = False
        self._search_gen = 0
        self._searched = False
        self._orphans = None
        self._addons = ListModel(ADDON_ROLES, self)
        self._clients_model = ListModel(CLIENT_ROLES, self)
        self._browse = ListModel(BROWSE_ROLES, self)

    @Slot(object)
    def _run(self, fn):
        fn()

    def _bg(self, fn, done=None):
        def job():
            try:
                result, err = fn(), None
            except SourceError as e:
                result, err = None, str(e)
            except Exception as e:
                result, err = None, f"{type(e).__name__}: {e}"
            if done:
                self._post.emit(lambda: done(result, err))

        self._pool.submit(job)

    def shutdown(self):
        self._gen += 1
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _client(self):
        return self._clients[self._index] if 0 <= self._index < len(self._clients) else None

    def _mgr(self, client):
        if client.id not in self._managers:
            self._managers[client.id] = Manager(client, self.cfg)
        return self._managers[client.id]

    def start(self):
        self._load_clients()
        if self._uri:
            ref = sources.parse_ref(self._uri)
            if ref:
                self.showBrowse.emit(ref)

    def _load_clients(self):
        current = self._client()
        want = current.id if current else self.cfg.get("last_client")
        self._clients = discover(self.cfg.get("extra_paths"))
        old = {r["key"]: r["updates"] for r in self._clients_model.rows()}
        self._clients_model.sync(
            [
                {
                    "key": c.id,
                    "label": c.label,
                    "location": c.location,
                    "version": c.version,
                    "updates": old.get(c.id, 0),
                }
                for c in self._clients
            ]
        )
        ids = [c.id for c in self._clients]
        self._index = ids.index(want) if want in ids else (0 if ids else -1)
        self.changed.emit()
        self.backupsChanged.emit()
        self._orphans = None
        self.orphansChanged.emit()
        self.refresh()
        for i, c in enumerate(self._clients):
            if i != self._index:
                self._recount(c)

    def _recount(self, client):
        mgr = self._mgr(client)

        def done(result, err):
            if result is not None:
                n = sum(1 for a, r, e in result if can_auto_update(a, r))
                self._clients_model.patch(client.id, updates=n)

        self._bg(lambda: survey(mgr), done)

    def _row(self, e):
        a, rel = e.addon, e.release
        update = needs_update(a, rel)
        action = ""
        if e.busy:
            status, text = "working", e.busy
        elif e.checking:
            status, text = "checking", "Checking"
        elif e.error:
            status, text, action = "error", e.error, "retry"
        elif not a.managed:
            if e.guess:
                status, text, action = "suggest", f"Looks like {e.guess_name} on WoWInterface", "accept"
            else:
                status, text, action = "unknown", a.note or "Source unknown", "link"
        elif a.missing:
            status, text, action = "error", "Files are missing", "reinstall"
        elif update and a.pinned:
            status, text = "pinned", f"Pinned, {rel.version} is out"
        elif update and a.modified:
            status, text, action = "modified", f"Changed by you, {rel.version} is out", "update"
        elif update:
            status, text, action = "update", f"{rel.version} available", "update"
        elif a.pinned:
            status, text = "pinned", "Pinned"
        elif a.modified:
            status, text = "modified", "Changed by you"
        else:
            status, text = "ok", "Up to date"
        return {
            "key": a.key,
            "name": a.name,
            "version": a.version,
            "latest": rel.version if rel and update else "",
            "source": sources.label(a.ref),
            "status": status,
            "statusText": text,
            "pinned": a.pinned,
            "modified": a.modified,
            "managed": a.managed,
            "progress": e.progress,
            "author": a.author,
            "page": a.page,
            "channel": a.channel,
            "action": action,
            "folders": len(a.dirs),
            "busy": bool(e.busy),
        }

    def _publish(self):
        words = self._filter.lower().split()
        rows = []
        for e in sorted(self._entries.values(), key=lambda x: x.addon.name.lower().lstrip("!")):
            hay = f"{e.addon.name} {e.addon.author} {' '.join(e.addon.dirs)}".lower()
            if all(w in hay for w in words):
                rows.append(self._row(e))
        self._addons.sync(rows)
        client = self._client()
        if client:
            self._clients_model.patch(client.id, updates=self._update_count())
        self.changed.emit()

    def _update_count(self):
        return sum(1 for e in self._entries.values() if can_auto_update(e.addon, e.release))

    def _check(self, addon, gen, client):
        mgr = self._mgr(client)

        def work():
            found, release, error = check_one(mgr, addon)
            guess = None
            if not found.managed and not error:
                guess = mgr.guess(found)
            return found, release, error, guess

        def done(result, err):
            if gen != self._gen:
                return
            e = self._entries.pop(addon.key, None)
            if e is None:
                return
            if result is None:
                e.error = err or "Check failed"
            else:
                e.addon, e.release, e.error, guess = result
                e.guess, e.guess_name, e.guess_dirs = guess or ("", "", [])
            e.checking = False
            self._entries[e.addon.key] = e
            self._publish()

        self._bg(work, done)

    @Slot()
    def refresh(self):
        client = self._client()
        self._gen += 1
        gen = self._gen
        if not client:
            self._entries = {}
            self._publish()
            return
        self._loading = True
        self._entries = {}
        self._publish()
        mgr = self._mgr(client)

        def done(addons, err):
            if gen != self._gen:
                return
            self._loading = False
            if err:
                self.toast.emit(err, True)
            self._entries = {a.key: Entry(a, True) for a in addons or []}
            self._publish()
            for a in addons or []:
                self._check(a, gen, client)

        self._bg(mgr.list, done)

    def _reload(self):
        client = self._client()
        if not client:
            return
        gen = self._gen
        mgr = self._mgr(client)

        def done(addons, err):
            if gen != self._gen or addons is None:
                return
            fresh = {}
            todo = []
            for a in addons:
                e = self._entries.get(a.key)
                if e:
                    e.addon = a
                else:
                    e = Entry(a, True)
                    todo.append(a)
                fresh[a.key] = e
            self._entries = fresh
            self._publish()
            for a in todo:
                self._check(a, gen, client)
            self._refresh_browse_flags(mgr)

        self._bg(mgr.list, done)

    def _refresh_browse_flags(self, mgr):
        refs = set(mgr.refs())
        for row in list(self._browse.rows()):
            if row["key"] in refs and not row["installed"]:
                self._browse.patch(row["key"], installed=True)

    def _progress_cb(self, gen, key, model=None):
        last = [0.0, 0.0]

        def cb(p):
            now = time.monotonic()
            if p < 1 and (p - last[0] < 0.02 or now - last[1] < 0.05):
                return
            last[0], last[1] = p, now
            self._post.emit(lambda: self._set_progress(gen, key, p, model))

        return cb

    def _set_progress(self, gen, key, p, model):
        if model is not None:
            model.patch(key, progress=p)
            return
        if gen != self._gen:
            return
        e = self._entries.get(key)
        if e and e.busy:
            e.progress = p
            self._addons.patch(key, progress=p)

    def _start_update(self, key, do_backup, force=False):
        e = self._entries.get(key)
        client = self._client()
        if not e or not client or not e.addon.managed:
            return
        gen = self._gen
        mgr = self._mgr(client)
        addon, release = e.addon, e.release
        e.busy = "Updating"
        e.progress = 0.0
        e.error = ""
        self._publish()
        progress = self._progress_cb(gen, key)

        def work():
            if do_backup and self.cfg.get("backup_on_update"):
                backup.create(client, self.cfg.get("backup_keep"))
            rel = release if release and not force else mgr.latest(addon)
            mgr.apply(addon.ref, rel, progress, addon.channel)
            return rel

        def done(rel, err):
            if gen != self._gen:
                self._recount(client)
                return
            e.busy = ""
            e.progress = 0.0
            if err:
                e.error = err
                self.toast.emit(f"{addon.name}: {err}", True)
            else:
                e.release = rel
            self._reload()
            self.backupsChanged.emit()

        self._bg(work, done)

    @Slot(str)
    def updateAddon(self, key):
        e = self._entries.get(key)
        if e and not e.busy:
            self._start_update(key, True)

    @Slot(str)
    def reinstall(self, key):
        e = self._entries.get(key)
        if e and not e.busy:
            self._start_update(key, True, force=True)

    @Slot()
    def updateAll(self):
        client = self._client()
        keys = [k for k, e in self._entries.items() if not e.busy and can_auto_update(e.addon, e.release)]
        if not client or not keys:
            return
        gen = self._gen
        for k in keys:
            self._entries[k].busy = "Waiting"
        self._publish()

        def work():
            if self.cfg.get("backup_on_update"):
                backup.create(client, self.cfg.get("backup_keep"))

        def done(result, err):
            if gen != self._gen:
                return
            self.backupsChanged.emit()
            for k in keys:
                self._start_update(k, False)

        self._bg(work, done)

    @Slot(str)
    def retry(self, key):
        e = self._entries.get(key)
        client = self._client()
        if e and client and not e.busy:
            e.error = ""
            e.checking = True
            self._publish()
            self._check(e.addon, self._gen, client)

    @Slot(str)
    def removeAddon(self, key):
        e = self._entries.get(key)
        client = self._client()
        if not e or not client or e.busy:
            return
        mgr = self._mgr(client)
        addon = e.addon
        e.busy = "Removing"
        self._publish()

        def done(result, err):
            e.busy = ""
            if err:
                self.toast.emit(err, True)
            else:
                self.toast.emit(f"Removed {addon.name}", False)
            self._reload()
            self._orphans = None
            self.orphansChanged.emit()

        self._bg(lambda: mgr.uninstall(addon), done)

    @Slot(str)
    def togglePin(self, key):
        e = self._entries.get(key)
        client = self._client()
        if e and client and e.addon.managed:
            self._mgr(client).set_field(e.addon.ref, "pinned", not e.addon.pinned)
            self._reload()

    @Slot(str, str)
    def setChannel(self, key, channel):
        e = self._entries.get(key)
        client = self._client()
        if e and client and e.addon.managed and channel in ("stable", "beta"):
            self._mgr(client).set_field(e.addon.ref, "channel", channel)
            e.addon.channel = channel
            self.retry(key)

    @Slot(str)
    def forget(self, key):
        e = self._entries.get(key)
        client = self._client()
        if e and client and e.addon.managed and not e.busy:
            self._mgr(client).unlink(e.addon.ref)
            self._entries.pop(key, None)
            self._reload()

    def _link(self, key, ref, extra_dirs=()):
        e = self._entries.get(key)
        client = self._client()
        if not e or not client or e.busy:
            return
        mgr = self._mgr(client)
        addon = e.addon
        e.busy = "Linking"
        self._publish()

        def done(release, err):
            e.busy = ""
            if err:
                self.toast.emit(err, True)
                self._publish()
                return
            self._entries.pop(key, None)
            self.toast.emit(f"{addon.name} now updates from {sources.label(ref)}", False)
            self._reload()

        self._bg(lambda: mgr.link(addon, ref, extra_dirs), done)

    @Slot(str)
    def acceptGuess(self, key):
        e = self._entries.get(key)
        if e and e.guess:
            self._link(key, e.guess, e.guess_dirs)

    @Slot(str, str, result=bool)
    def linkAddon(self, key, text):
        ref = sources.parse_ref(text)
        if not ref:
            self.toast.emit("That is not a link wowam knows", True)
            return False
        self._link(key, ref)
        return True

    @Slot(str)
    def openFolder(self, key):
        e = self._entries.get(key)
        client = self._client()
        if e and client and e.addon.dirs:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(client.addons_dir / e.addon.dirs[0])))

    @Slot(str)
    def openUrl(self, url):
        if url.startswith(("https://", "http://")):
            QDesktopServices.openUrl(QUrl(url))

    @Slot(str)
    def setFilter(self, text):
        self._filter = text
        self._publish()

    @Slot(int)
    def selectClient(self, i):
        if 0 <= i < len(self._clients) and i != self._index:
            self._index = i
            self.cfg.set("last_client", self._clients[i].id)
            self._browse.sync([])
            self._searched = False
            self.browseChanged.emit()
            self._orphans = None
            self.orphansChanged.emit()
            self.backupsChanged.emit()
            self.refresh()

    @Slot(str)
    def search(self, text):
        client = self._client()
        text = text.strip()
        self._search_gen += 1
        gen = self._search_gen
        if not client or not text:
            self._browse.sync([])
            self._searching = False
            self._searched = False
            self.browseChanged.emit()
            return
        self._searching = True
        self.browseChanged.emit()
        mgr = self._mgr(client)

        def work():
            return sources.search(text, client, self.cfg), set(mgr.refs()), mgr.all_dirs()

        def done(result, err):
            if gen != self._search_gen:
                return
            self._searching = False
            self._searched = True
            rows = []
            if err:
                self.toast.emit(err, True)
            else:
                found, refs, present = result
                seen = set()
                for r in found:
                    if r["ref"] in seen:
                        continue
                    seen.add(r["ref"])
                    rows.append(
                        {
                            "key": r["ref"],
                            "name": r["name"],
                            "author": r["author"],
                            "version": r["version"],
                            "source": r["source"],
                            "summary": r["summary"],
                            "compatible": r["compatible"],
                            "page": r["page"],
                            "installed": r["ref"] in refs or bool(r["dirs"] and set(r["dirs"]) <= present),
                            "busy": False,
                            "progress": 0.0,
                        }
                    )
            self._browse.sync(rows)
            self.browseChanged.emit()

        self._bg(work, done)

    def _install(self, ref, quiet=False):
        client = self._client()
        if not client:
            return
        mgr = self._mgr(client)
        self._browse.patch(ref, busy=True, progress=0.0)
        progress = self._progress_cb(self._gen, ref, self._browse)

        def done(rec, err):
            self._browse.patch(ref, busy=False, progress=0.0)
            if err:
                self.toast.emit(f"{ref}: {err}" if quiet else err, True)
            else:
                self._browse.patch(ref, installed=True)
                self.toast.emit(f"Installed {rec['name']} on {client.label}", False)
            if client is self._client():
                self._reload()
            else:
                self._recount(client)

        self._bg(lambda: mgr.install(ref, progress), done)

    @Slot(str)
    def installRef(self, ref):
        self._install(ref)

    @Slot(str, result=int)
    def installList(self, text):
        refs = parse_refs(text)
        for ref in refs:
            self._install(ref, quiet=True)
        if not refs:
            self.toast.emit("No addon links found in that text", True)
        return len(refs)

    @Slot()
    def copyList(self):
        client = self._client()
        if not client:
            return
        refs = self._mgr(client).refs()
        QGuiApplication.clipboard().setText(" ".join(refs))
        self.toast.emit(f"Copied {len(refs)} addons to the clipboard", False)

    @Slot()
    def backupNow(self):
        client = self._client()
        if not client:
            return

        def done(path, err):
            if err or not path:
                self.toast.emit(err or "There are no settings to back up yet", True)
            else:
                self.toast.emit("Backup saved", False)
            self.backupsChanged.emit()

        self._bg(lambda: backup.create(client, self.cfg.get("backup_keep")), done)

    @Slot(str)
    def restoreBackup(self, name):
        client = self._client()
        if not client:
            return

        def done(result, err):
            if err:
                self.toast.emit(f"Restore failed: {err}", True)
            else:
                self.toast.emit("Settings restored", False)
            self.backupsChanged.emit()

        self._bg(lambda: backup.restore(client, name), done)

    @Slot()
    def scanOrphans(self):
        client = self._client()
        if not client:
            return
        mgr = self._mgr(client)

        def done(found, err):
            if client is not self._client():
                return
            self._orphans = found or []
            self.orphansChanged.emit()

        self._bg(mgr.orphans, done)

    @Slot()
    def cleanOrphans(self):
        client = self._client()
        if not client:
            return
        mgr = self._mgr(client)

        def work():
            backup.create(client, self.cfg.get("backup_keep"))
            return mgr.clean_orphans()

        def done(count, err):
            if err:
                self.toast.emit(err, True)
            else:
                self.toast.emit("Deleted 1 leftover file" if count == 1 else f"Deleted {count} leftover files", False)
            self._orphans = None
            self.orphansChanged.emit()
            self.backupsChanged.emit()

        self._bg(work, done)

    @Slot(str)
    def addFolder(self, url):
        path = QUrl(url).toLocalFile() if "://" in url else url
        if not path:
            return
        before = {c.id for c in discover(self.cfg.get("extra_paths"))}
        after = {c.id for c in discover(list(self.cfg.get("extra_paths")) + [path])}
        if after == before:
            self.toast.emit("No new WoW install was found in that folder", True)
            return
        self.cfg.set("extra_paths", list(self.cfg.get("extra_paths")) + [path])
        self._load_clients()
        self.settingsChanged.emit()
        self.toast.emit(f"Added {len(after - before)} install(s)", False)

    @Slot(str)
    def removeFolder(self, path):
        self.cfg.set("extra_paths", [p for p in self.cfg.get("extra_paths") if p != path])
        self._load_clients()
        self.settingsChanged.emit()

    @Slot(str, str)
    def setText(self, key, value):
        if key in ("github_token", "wago_key"):
            self.cfg.set(key, value.strip())
            self.settingsChanged.emit()

    @Slot(bool)
    def setBackupOnUpdate(self, on):
        self.cfg.set("backup_on_update", bool(on))
        self.settingsChanged.emit()

    @Slot(int)
    def setBackupKeep(self, n):
        self.cfg.set("backup_keep", max(1, min(50, n)))
        self.settingsChanged.emit()

    @Slot(bool)
    def setLauncher(self, on):
        try:
            desktop.install_launcher() if on else desktop.remove_launcher()
        except OSError as e:
            self.toast.emit(str(e), True)
        self.settingsChanged.emit()

    @Slot(bool)
    def setTimer(self, on):
        def done(ok, err):
            if on and not ok:
                self.toast.emit("Could not turn on background updates", True)
            self.settingsChanged.emit()

        self._bg(desktop.enable_timer if on else desktop.disable_timer, done)

    @Property(QObject, constant=True)
    def addons(self):
        return self._addons

    @Property(QObject, constant=True)
    def clients(self):
        return self._clients_model

    @Property(QObject, constant=True)
    def browse(self):
        return self._browse

    @Property(str, constant=True)
    def version(self):
        return __version__

    @Property(str, constant=True)
    def themeMode(self):
        return os.environ.get("WOWAM_THEME", "")

    @Property(int, notify=changed)
    def currentIndex(self):
        return self._index

    @Property(bool, notify=changed)
    def hasClient(self):
        return self._client() is not None

    @Property(str, notify=changed)
    def clientLabel(self):
        c = self._client()
        return c.label if c else ""

    @Property(str, notify=changed)
    def clientPath(self):
        c = self._client()
        return str(c.path) if c else ""

    @Property(str, notify=changed)
    def clientVersion(self):
        c = self._client()
        return c.version if c else ""

    @Property(int, notify=changed)
    def addonCount(self):
        return len(self._entries)

    @Property(int, notify=changed)
    def updateCount(self):
        return self._update_count()

    @Property(bool, notify=changed)
    def loading(self):
        return self._loading

    @Property(bool, notify=changed)
    def checking(self):
        return self._loading or any(e.checking for e in self._entries.values())

    @Property(bool, notify=changed)
    def working(self):
        return any(e.busy for e in self._entries.values())

    @Property(bool, notify=browseChanged)
    def searching(self):
        return self._searching

    @Property(bool, notify=browseChanged)
    def searched(self):
        return self._searched

    @Property(str, notify=settingsChanged)
    def githubToken(self):
        return self.cfg.get("github_token")

    @Property(str, notify=settingsChanged)
    def wagoKey(self):
        return self.cfg.get("wago_key")

    @Property(bool, notify=settingsChanged)
    def backupOnUpdate(self):
        return bool(self.cfg.get("backup_on_update"))

    @Property(int, notify=settingsChanged)
    def backupKeep(self):
        return int(self.cfg.get("backup_keep"))

    @Property(bool, notify=settingsChanged)
    def launcher(self):
        return desktop.launcher_installed()

    @Property(bool, notify=settingsChanged)
    def timer(self):
        return desktop.timer_enabled()

    @Property("QVariantList", notify=settingsChanged)
    def extraPaths(self):
        return list(self.cfg.get("extra_paths"))

    @Property("QVariantList", notify=backupsChanged)
    def backups(self):
        c = self._client()
        if not c:
            return []
        out = []
        for b in backup.entries(c):
            when = time.strftime("%d %b %Y, %H:%M", time.localtime(b["time"]))
            out.append({"name": b["name"], "when": when, "size": human_size(b["size"])})
        return out

    @Property(bool, notify=orphansChanged)
    def orphansScanned(self):
        return self._orphans is not None

    @Property(int, notify=orphansChanged)
    def orphanCount(self):
        return len(self._orphans or [])

    @Property(str, notify=orphansChanged)
    def orphanSummary(self):
        found = self._orphans or []
        if not found:
            return "Nothing left behind."
        names = sorted({o["addon"] for o in found}, key=str.lower)
        shown = ", ".join(names[:6]) + (f" and {len(names) - 6} more" if len(names) > 6 else "")
        size = human_size(sum(o["size"] for o in found))
        files = "1 file" if len(found) == 1 else f"{len(found)} files"
        return f"{files} ({size}) from addons that are no longer installed: {shown}"


def run(uri=""):
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("wowam")
    app.setApplicationDisplayName("wowam")
    app.setDesktopFileName("wowam")
    app.setWindowIcon(QIcon(str(desktop.icon_source())))
    backend = Backend(uri)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Wowam" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    backend.start()
    code = app.exec()
    backend.shutdown()
    del engine
    return code
