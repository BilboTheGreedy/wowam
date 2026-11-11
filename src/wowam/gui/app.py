import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import Property, QAbstractListModel, QEvent, QModelIndex, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .. import __version__, auras, backup, desktop, history, http, launch, lists, selfupdate, sources
from ..cli import update_client
from ..clients import discover
from ..config import Config
from ..manager import Manager, can_auto_update, check_one, needs_update, parse_refs, survey
from ..sources import SourceError

QML_DIR = Path(__file__).resolve().parent / "qml"

ADDON_ROLES = [
    "key", "name", "version", "latest", "source", "status", "statusText", "pinned", "modified", "managed",
    "progress", "author", "page", "channel", "action", "folders", "busy", "previous", "notes", "outdated", "needs",
]
CLIENT_ROLES = ["key", "label", "location", "version", "updates"]
BROWSE_ROLES = [
    "key", "name", "author", "version", "source", "summary", "listed", "page", "installed", "busy", "progress",
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
    updateChanged = Signal()
    historyChanged = Signal()
    aurasChanged = Signal()
    sharedChanged = Signal()
    listReady = Signal("QVariant")
    shareRequested = Signal("QVariant")
    published = Signal(str)

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
        self._shared = []
        self._shared_at = 0
        self._shared_busy = False
        self._search_gen = 0
        self._searched = False
        self._orphans = None
        self._update = None
        self._updating = False
        self._update_progress = 0.0
        self._auto_done = set()
        self._found = []
        self._auras = []
        self.tray_available = False
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
        self._bg(selfupdate.cleanup)
        self._bg(desktop.refresh_launcher)
        if self.cfg.get("check_updates"):
            self._bg(selfupdate.check, self._update_found)
        if self._uri:
            ref = sources.parse_ref(self._uri)
            if ref:
                self.showBrowse.emit(ref)

    def _update_found(self, info, err):
        self._update = info
        self.updateChanged.emit()

    @Slot()
    def installUpdate(self):
        info = self._update
        if not info or self._updating:
            return
        if not info.get("url"):
            self.openUrl(info["page"])
            return
        self._updating = True
        self._update_progress = 0.0
        self.updateChanged.emit()
        last = [0.0]

        def progress(p):
            if p - last[0] >= 0.02 or p >= 1:
                last[0] = p
                self._post.emit(lambda: self._set_update_progress(p))

        def work():
            try:
                selfupdate.install(info, progress)
            except selfupdate.UpdateError as e:
                raise SourceError(str(e)) from e

        def done(result, err):
            if err:
                self._updating = False
                self.updateChanged.emit()
                self.toast.emit(err, True)
                return
            QGuiApplication.quit()

        self._bg(work, done)

    def _set_update_progress(self, p):
        self._update_progress = p
        self.updateChanged.emit()

    @Slot()
    def dismissUpdate(self):
        if not self._updating:
            self._update = None
            self.updateChanged.emit()

    def _auto_update(self):
        client = self._client()
        if not client or not self.cfg.get("update_on_start") or client.id in self._auto_done:
            return
        if self._loading or any(e.checking for e in self._entries.values()):
            return
        self._auto_done.add(client.id)
        if self._update_count():
            self.updateAll()

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

        def work():
            if self.cfg.get("update_on_start") and client.id not in self._auto_done:
                self._auto_done.add(client.id)
                update_client(client, self.cfg, quiet=True)
            if self.cfg.get("aura_updates"):
                try:
                    auras.sync(client)
                except OSError:
                    pass
            return survey(mgr)

        def done(result, err):
            if result is not None:
                n = sum(1 for a, r, e in result if can_auto_update(a, r))
                self._clients_model.patch(client.id, updates=n)
                self.changed.emit()

        self._bg(work, done)

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
        elif a.needs:
            more = f" and {len(a.needs) - 1} more" if len(a.needs) > 1 else ""
            status, text, action = "modified", f"Needs {a.needs[0]}{more}", "find"
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
            "previous": a.previous,
            "notes": bool(rel and rel.notes),
            "outdated": a.outdated,
            "needs": a.needs[0] if a.needs else "",
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
            self._auto_update()

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
        self._sync_auras(client, gen)

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

    def _sync_auras(self, client, gen):
        self._auras = []
        self.aurasChanged.emit()
        if not self.cfg.get("aura_updates"):
            return

        def done(found, err):
            if gen == self._gen and found:
                self._auras = found
                self.aurasChanged.emit()

        self._bg(lambda: auras.sync(client), done)

    @Property(int, notify=aurasChanged)
    def auraCount(self):
        return len(self._auras)

    @Property(str, notify=aurasChanged)
    def auraSummary(self):
        names = [a["name"] for a in self._auras]
        return ", ".join(names[:4]) + (f" and {len(names) - 4} more" if len(names) > 4 else "")

    @Property(bool, notify=settingsChanged)
    def auraUpdates(self):
        return bool(self.cfg.get("aura_updates"))

    @Slot(bool)
    def setAuraUpdates(self, on):
        self.cfg.set("aura_updates", bool(on))
        self.settingsChanged.emit()
        client = self._client()
        if on and client:
            self._sync_auras(client, self._gen)
        elif not on:
            for c in self._clients:
                auras.remove(c)
            self._auras = []
            self.aurasChanged.emit()

    @Property("QVariantList", notify=changed)
    def otherClients(self):
        current = self._client()
        return [{"key": c.id, "label": c.label} for c in self._clients if c is not current]

    @Slot(str)
    def copyFrom(self, key):
        client = self._client()
        other = next((c for c in self._clients if c.id == key), None)
        if not client or not other or other is client:
            return
        have = set(self._mgr(client).refs())
        refs = [r for r in self._mgr(other).refs() if r not in have]
        if not refs:
            self.toast.emit(f"{client.label} already has every addon from {other.label}", False)
            return
        count = "1 addon" if len(refs) == 1 else f"{len(refs)} addons"
        self.toast.emit(f"Installing {count} from {other.label}", False)
        for ref in refs:
            self._install(ref, quiet=True)

    @Property(str, notify=changed)
    def playTip(self):
        client = self._client()
        found = launch.plan(client) if client else None
        return found[2] if found else ""

    @Slot()
    def play(self):
        client = self._client()
        try:
            started = bool(client) and launch.start(client)
        except OSError as e:
            self.toast.emit(str(e), True)
            return
        if started:
            self.toast.emit("Starting the game", False)
        else:
            self.toast.emit("Could not find a way to start this install", True)

    @Property(bool, notify=settingsChanged)
    def trayAvailable(self):
        return self.tray_available

    @Property(bool, notify=settingsChanged)
    def trayOn(self):
        return self.tray_available and bool(self.cfg.get("tray"))

    @Slot(bool)
    def setTray(self, on):
        self.cfg.set("tray", bool(on))
        self.settingsChanged.emit()

    @Slot()
    def recheck(self):
        self._auto_done.clear()
        self._load_clients()

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
        for row in self._found:
            if row["key"] in refs and not row["installed"]:
                row["installed"] = True
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
            self.historyChanged.emit()

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

    @Slot(str)
    def rollback(self, key):
        e = self._entries.get(key)
        client = self._client()
        if not e or not client or e.busy or not e.addon.previous:
            return
        mgr = self._mgr(client)
        addon = e.addon
        e.busy = "Going back"
        self._publish()

        def done(rec, err):
            e.busy = ""
            if err:
                self.toast.emit(f"{addon.name}: {err}", True)
            else:
                self.toast.emit(f"{addon.name} is back on {rec['version']} and pinned", False)
            self._reload()
            self.historyChanged.emit()

        self._bg(lambda: mgr.rollback(addon.ref), done)

    @Slot(str, result="QVariantMap")
    def notesFor(self, key):
        e = self._entries.get(key)
        if not e or not e.release:
            return {"title": "", "text": "", "markdown": False}
        return {
            "title": f"{e.addon.name} {e.release.version}",
            "text": e.release.notes,
            "markdown": e.addon.ref.startswith("gh:"),
        }

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
            self._found = []
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
        if client and lists.list_url(text):
            self.openListUrl(text)
            text = ""
        if not client or not text:
            self._found = []
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
                            "listed": r["listed"],
                            "page": r["page"],
                            "installed": r["ref"] in refs or bool(r["dirs"] and set(r["dirs"]) <= present),
                            "busy": False,
                            "progress": 0.0,
                        }
                    )
            self._found = rows
            self._show_found()

        self._bg(work, done)

    def _listed_only(self):
        choice = self.cfg.get("browse_listed")
        if choice in ("on", "off"):
            return choice == "on"
        client = self._client()
        return bool(client and client.flavor != "mainline")

    def _show_found(self):
        rows = self._found
        if self._listed_only():
            rows = [r for r in rows if r["listed"] in ("yes", "direct")]
        self._browse.sync(rows)
        self.browseChanged.emit()

    @Slot(bool)
    def setListedOnly(self, on):
        self.cfg.set("browse_listed", "on" if on else "off")
        self._show_found()

    @Property(bool, notify=browseChanged)
    def listedOnly(self):
        return self._listed_only()

    @Property(int, notify=browseChanged)
    def hiddenResults(self):
        return len(self._found) - self._browse.count

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
                self.historyChanged.emit()
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
        if lists.list_url(text):
            self.openListUrl(text)
            return 1
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

    @Property("QVariantList", notify=sharedChanged)
    def sharedLists(self):
        keys = ("slug", "name", "by", "game", "about")
        return [{**{k: i[k] for k in keys}, "count": len(i["refs"])} for i in self._shared]

    @Property(str, constant=True)
    def listsPage(self):
        return lists.PAGE

    @Slot()
    def loadShared(self):
        if self._shared_busy or time.time() - self._shared_at < 3600:
            return
        self._shared_busy = True

        def done(result, err):
            self._shared_busy = False
            if result is not None:
                self._shared = result
                self._shared_at = time.time()
                self.sharedChanged.emit()

        self._bg(lists.shared, done)

    def _show_list(self, item):
        client = self._client()
        have = set(self._mgr(client).refs()) if client else set()
        missing = [r for r in item["refs"] if r not in have]
        self.listReady.emit({
            "name": item["name"],
            "by": item["by"],
            "game": item["game"],
            "about": item["about"],
            "refs": [{"ref": r, "have": r in have} for r in item["refs"]],
            "missing": " ".join(missing),
            "count": len(missing),
        })

    @Slot(str)
    def openShared(self, slug):
        item = next((i for i in self._shared if i["slug"] == slug), None)
        if item:
            self._show_list(item)

    @Slot(str)
    def openListUrl(self, text):
        url = lists.list_url(text)
        if not url:
            return

        def done(result, err):
            if err:
                self.toast.emit(err, True)
            else:
                self._show_list(result)

        self._bg(lambda: lists.fetch(url), done)

    @Slot()
    def openShare(self):
        client = self._client()
        if not client:
            return
        mgr = self._mgr(client)
        mgr.refs()
        items = [{"ref": ref, "name": rec.get("name") or ref} for ref, rec in mgr.state.addons.items()]
        if not items:
            self.toast.emit("Install some addons first, then share the list", True)
            return
        items.sort(key=lambda i: i["name"].lower())
        self.shareRequested.emit({"items": items, "game": client.label, "shared": client.id in self.cfg.get("gists")})

    @Slot(str, str, str)
    def publishList(self, name, about, text):
        client = self._client()
        refs = parse_refs(text)
        if not client or not refs:
            self.toast.emit("Pick at least one addon", True)
            return
        gists = dict(self.cfg.get("gists"))
        name = name.strip() or "My setup"

        def done(result, err):
            if err:
                self.toast.emit(err, True)
                self.published.emit("")
                return
            gists[client.id] = result["id"]
            self.cfg.set("gists", gists)
            QGuiApplication.clipboard().setText(result["url"])
            self.published.emit(result["url"])

        self._bg(lambda: lists.publish(self.cfg, refs, name, about, client.label, gists.get(client.id, "")), done)

    @Slot(str)
    def copyText(self, text):
        QGuiApplication.clipboard().setText(text)
        self.toast.emit("Copied", False)

    @Slot()
    def shareList(self):
        client = self._client()
        refs = self._mgr(client).refs() if client else []
        if not refs:
            self.toast.emit("Install some addons first, then share the list", True)
            return
        text = lists.template(refs, client.label)
        QGuiApplication.clipboard().setText(text)
        self.openUrl(lists.share_url(text))
        self.toast.emit("Opening GitHub. Your list is also on the clipboard.", False)

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
        if key in ("github_token", "wago_key", "curseforge_key"):
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

    @Slot(bool)
    def setAutostart(self, on):
        try:
            desktop.enable_autostart() if on else desktop.disable_autostart()
        except OSError as e:
            self.toast.emit(str(e), True)
        self.settingsChanged.emit()

    @Slot(bool)
    def setUpdateOnStart(self, on):
        self.cfg.set("update_on_start", bool(on))
        self.settingsChanged.emit()

    @Property(bool, notify=settingsChanged)
    def welcomeNeeded(self):
        return not self.cfg.get("welcomed")

    @Slot()
    def setWelcomed(self):
        if not self.cfg.get("welcomed"):
            self.cfg.set("welcomed", True)
            self.settingsChanged.emit()

    @Slot(str)
    def setTheme(self, mode):
        if mode in ("", "light", "dark"):
            self.cfg.set("theme", mode)
            self.settingsChanged.emit()

    @Slot(bool)
    def setCheckUpdates(self, on):
        self.cfg.set("check_updates", bool(on))
        self.settingsChanged.emit()
        if on and not self._update:
            self._bg(selfupdate.check, self._update_found)

    @Property(bool, notify=settingsChanged)
    def autostart(self):
        return desktop.autostart_enabled()

    @Property(bool, notify=settingsChanged)
    def updateOnStart(self):
        return bool(self.cfg.get("update_on_start"))

    @Property(bool, notify=settingsChanged)
    def checkUpdates(self):
        return bool(self.cfg.get("check_updates"))

    @Property(str, notify=updateChanged)
    def updateVersion(self):
        return self._update["version"] if self._update else ""

    @Property(bool, notify=updateChanged)
    def updateInstallable(self):
        return bool(self._update and self._update.get("url"))

    @Property(bool, notify=updateChanged)
    def updating(self):
        return self._updating

    @Property(float, notify=updateChanged)
    def updateProgress(self):
        return self._update_progress

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
    def appName(self):
        return desktop.APP_NAME

    @Property(str, constant=True)
    def fullName(self):
        return desktop.FULL_NAME

    @Property(str, notify=settingsChanged)
    def themeMode(self):
        return os.environ.get("WOWAM_THEME") or self.cfg.get("theme")

    @Property("QVariantList", notify=historyChanged)
    def history(self):
        out = []
        for row in history.entries()[:15]:
            when = time.strftime("%d %b, %H:%M", time.localtime(row.get("time", 0)))
            old, new = row.get("old", ""), row.get("new", "")
            change = f"{old} → {new}" if old else f"installed {new}"
            out.append({"name": row.get("name", ""), "change": change, "where": row.get("client", ""), "when": when})
        return out

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

    @Property(str, notify=settingsChanged)
    def curseKey(self):
        return self.cfg.get("curseforge_key")

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


class UrlFilter(QObject):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FileOpen:
            ref = sources.parse_ref(event.url().toString())
            if ref:
                self.backend.showBrowse.emit(ref)
                return True
        return False


class Tray(QObject):
    def __init__(self, app, backend, window):
        super().__init__(app)
        self.app = app
        self.backend = backend
        self.window = window
        self.seen = 0
        self.icon = QSystemTrayIcon(app.windowIcon(), self)
        self.menu = QMenu()
        for text, fn in (
            ("Open", self.show),
            ("Check for updates", backend.recheck),
            ("Update all", backend.updateAll),
            (None, None),
            ("Quit", app.quit),
        ):
            if text is None:
                self.menu.addSeparator()
                continue
            action = QAction(text, self.menu)
            action.triggered.connect(fn)
            self.menu.addAction(action)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self.clicked)
        self.timer = QTimer(self)
        self.timer.setInterval(2 * 3600 * 1000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        backend.settingsChanged.connect(self.apply)
        backend.changed.connect(self.status)
        self.apply()

    def apply(self):
        on = bool(self.backend.cfg.get("tray"))
        self.icon.setVisible(on)
        self.app.setQuitOnLastWindowClosed(not on)

    def show(self):
        self.window.show()
        self.window.raise_()
        self.window.requestActivate()

    def clicked(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.window.isVisible():
                self.window.hide()
            else:
                self.show()

    def tick(self):
        if not self.window.isVisible() and self.backend.cfg.get("tray"):
            self.backend.recheck()

    def status(self):
        rows = self.backend.clients.rows()
        count = sum(r["updates"] for r in rows)
        tip = desktop.FULL_NAME
        if count:
            tip += "\n" + ("1 addon update ready" if count == 1 else f"{count} addon updates ready")
        self.icon.setToolTip(tip)
        if self.backend.checking:
            return
        if count > self.seen and not self.window.isVisible() and self.icon.isVisible():
            text = "1 addon update is ready" if count == 1 else f"{count} addon updates are ready"
            self.icon.showMessage(desktop.APP_NAME, text, self.app.windowIcon(), 6000)
        self.seen = count


def run(uri="", hidden=False):
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("wowam")
    app.setApplicationDisplayName(desktop.FULL_NAME)
    app.setDesktopFileName("wowam")
    app.setWindowIcon(QIcon(str(desktop.icon_source())))
    backend = Backend(uri)
    urls = UrlFilter(backend)
    app.installEventFilter(urls)
    engine = QQmlApplicationEngine()
    smoke = os.environ.get("WOWAM_SMOKE")
    problems = []
    if smoke:
        engine.warnings.connect(lambda ws: problems.extend(w.toString() for w in ws))
    engine.addImportPath(str(QML_DIR))
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Wowam" / "Main.qml")))
    if not engine.rootObjects():
        if smoke:
            Path(smoke).write_text("load failed\n" + "\n".join(problems))
        return 1
    window = engine.rootObjects()[0]
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        backend.tray_available = True
        tray = Tray(app, backend, window)
        backend.settingsChanged.emit()
    if hidden and backend.trayOn and not uri:
        window.hide()
    else:
        window.show()
    backend.start()
    if smoke:
        QTimer.singleShot(4000, app.quit)
    code = app.exec()
    if smoke:
        try:
            http.final_url("https://github.com/")
        except http.HttpError as e:
            problems.append(str(e))
        Path(smoke).write_text("\n".join(problems) if problems else "ok")
        code = 2 if problems else code
    backend.shutdown()
    del tray
    del engine
    return code
