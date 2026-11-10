import hashlib
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace

from . import http, installer, sources, toc
from .known import KNOWN
from .paths import cache_dir
from .sources import SourceError
from .state import State

GITHUB_REPO = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)", re.I)
GITHUB_OWNER = re.compile(r"github\.com/([\w.-]+)/?$", re.I)
SV_GLOBS = ("Account/*/SavedVariables/*.lua*", "Account/*/*/*/SavedVariables/*.lua*")


@dataclass
class Addon:
    key: str
    name: str
    version: str
    dirs: list
    ref: str = ""
    managed: bool = False
    pinned: bool = False
    modified: bool = False
    missing: bool = False
    channel: str = "stable"
    author: str = ""
    page: str = ""
    note: str = ""
    candidates: list = field(default_factory=list)


def norm_version(v):
    v = (v or "").strip().lower()
    return v[1:] if v.startswith("v") and len(v) > 1 and v[1].isdigit() else v


def same_version(a, b):
    a, b = norm_version(a), norm_version(b)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    if len(short) < 3:
        return False
    for token in (short, "v" + short):
        if re.search(rf"(?<![\w.]){re.escape(token)}(?![\w.])", long):
            return True
    return False


class Manager:
    def __init__(self, client, cfg):
        self.client = client
        self.cfg = cfg
        self.state = State(client)
        self.lock = threading.RLock()

    def all_dirs(self):
        try:
            return {p.name for p in self.client.addons_dir.iterdir() if p.is_dir() and not p.name.startswith(".")}
        except OSError:
            return set()

    def folders(self):
        out = set()
        for name in self.all_dirs():
            if name.startswith("Blizzard_"):
                continue
            if toc.find(self.client.addons_dir / name, self.client.flavor):
                out.add(name)
        return out

    def _fingerprints(self, dirs):
        hashes, stamps = {}, {}
        for d in dirs:
            path = self.client.addons_dir / d
            if path.is_dir():
                hashes[d] = installer.dir_hash(path)
                stamps[d] = installer.dir_stamp(path)
        return hashes, stamps

    def _modified(self, rec):
        dirty = False
        changed = False
        stamps = rec.setdefault("stamps", {})
        for d in rec.get("dirs", []):
            path = self.client.addons_dir / d
            if not path.is_dir():
                changed = True
                continue
            stamp = installer.dir_stamp(path)
            if stamps.get(d) == stamp:
                continue
            if installer.dir_hash(path) == rec.get("hashes", {}).get(d):
                stamps[d] = stamp
                dirty = True
            else:
                changed = True
        return changed, dirty

    def _candidates(self, root, fields):
        out = []
        note = ""
        if root in KNOWN:
            out.append(KNOWN[root])
        for value in fields.values():
            m = GITHUB_REPO.search(value)
            if m:
                repo = m.group(2)[:-4] if m.group(2).endswith(".git") else m.group(2)
                out.append(f"gh:{m.group(1)}/{repo}")
                continue
            m = GITHUB_OWNER.search(value.strip())
            if m:
                out.append(f"gh:{m.group(1)}/{root.lstrip('!')}")
        wowi = fields.get("x-wowi-id", "")
        if wowi.isdigit():
            out.append(f"wowi:{wowi}")
        wago = fields.get("x-wago-id", "")
        if wago:
            if self.cfg.get("wago_key"):
                out.append(f"wago:{wago}")
            else:
                note = "On Wago Addons, which needs an API key"
        seen = []
        for ref in out:
            if ref not in seen:
                seen.append(ref)
        return seen, note

    def _groups(self, rest):
        tocs = {f: toc.read(self.client.addons_dir / f, self.client.flavor) for f in rest}

        def parent(f):
            fields = tocs[f]
            part = fields.get("x-part-of", "")
            if part in tocs and part != f:
                return part
            wanted = toc.deps(fields)
            version = fields.get("version", "")
            best = None
            for p in tocs:
                if p == f or not f.startswith(p) or len(f) <= len(p):
                    continue
                linked = f[len(p)] in "_-" or p in wanted or (version and version == tocs[p].get("version", ""))
                if linked and (best is None or len(p) > len(best)):
                    best = p
            return best

        roots = {}
        for f in sorted(rest):
            seen = {f}
            cur = f
            while True:
                up = parent(cur)
                if not up or up in seen:
                    break
                seen.add(up)
                cur = up
            roots.setdefault(cur, []).append(f)
        return roots, tocs

    def list(self):
        with self.lock:
            self.state.load()
            folders = self.folders()
            out = []
            owned = set()
            dirty = False
            for ref, rec in self.state.addons.items():
                dirs = list(rec.get("dirs", []))
                owned.update(dirs)
                present = [d for d in dirs if (self.client.addons_dir / d).is_dir()]
                modified = False
                if present:
                    modified, touched = self._modified(rec)
                    dirty = dirty or touched
                out.append(
                    Addon(
                        key=ref,
                        ref=ref,
                        name=rec.get("name") or ref,
                        version=rec.get("version", ""),
                        dirs=dirs,
                        managed=True,
                        pinned=bool(rec.get("pinned")),
                        modified=modified,
                        missing=not present,
                        channel=rec.get("channel", "stable"),
                        author=rec.get("author", ""),
                        page=rec.get("page", "") or sources.page_of(ref),
                    )
                )
            if dirty:
                self.state.save()
            roots, tocs = self._groups(folders - owned)
            for root, dirs in roots.items():
                fields = tocs[root]
                candidates, note = self._candidates(root, fields)
                out.append(
                    Addon(
                        key=f"local:{root}",
                        name=toc.clean(fields.get("title", "")) or root,
                        version=fields.get("version", ""),
                        dirs=sorted(dirs),
                        author=fields.get("author", ""),
                        note=note,
                        candidates=candidates,
                    )
                )
            out.sort(key=lambda a: a.name.lower().lstrip("!"))
            return out

    def get(self, key):
        return next((a for a in self.list() if a.key == key), None)

    def latest(self, addon):
        return sources.latest(addon.ref, self.client, self.cfg, addon.channel)

    def identify(self, addon):
        for ref in addon.candidates:
            try:
                release = sources.latest(ref, self.client, self.cfg)
            except SourceError:
                continue
            self.adopt(addon, ref, release)
            adopted = replace(
                addon,
                key=ref,
                ref=ref,
                managed=True,
                name=release.name or addon.name,
                author=release.author or addon.author,
                page=release.page or sources.page_of(ref),
                candidates=[],
                note="",
            )
            return adopted, release
        return None, None

    def guess(self, addon):
        root = addon.key.split(":", 1)[1]
        try:
            hits = sources.wowi_by_dir(root)
        except SourceError:
            return None
        if not hits:
            return None
        return f"wowi:{hits[0]['UID']}", hits[0].get("UIName", ""), list(hits[0].get("UIDir") or [])

    def adopt(self, addon, ref, release):
        with self.lock:
            self.state.load()
            dirs = [d for d in addon.dirs if (self.client.addons_dir / d).is_dir()]
            for other, rec in list(self.state.addons.items()):
                if other != ref and set(rec.get("dirs", [])) & set(dirs):
                    del self.state.addons[other]
            hashes, stamps = self._fingerprints(dirs)
            self.state.addons[ref] = {
                "name": release.name or addon.name,
                "version": addon.version,
                "dirs": dirs,
                "hashes": hashes,
                "stamps": stamps,
                "pinned": addon.pinned,
                "channel": addon.channel,
                "author": release.author or addon.author,
                "page": release.page or sources.page_of(ref),
                "adopted": True,
                "time": int(time.time()),
            }
            self.state.save()

    def link(self, addon, ref, extra_dirs=()):
        release = sources.latest(ref, self.client, self.cfg)
        if extra_dirs:
            with self.lock:
                self.state.load()
                owned = {d for rec in self.state.addons.values() for d in rec.get("dirs", [])}
            more = [d for d in extra_dirs if d not in addon.dirs and d not in owned and "/" not in d]
            addon = replace(addon, dirs=sorted(set(addon.dirs) | set(more)))
        self.adopt(addon, ref, release)
        return release

    def unlink(self, ref):
        with self.lock:
            self.state.load()
            if self.state.addons.pop(ref, None) is not None:
                self.state.save()

    def install(self, ref, progress=None, channel=None):
        with self.lock:
            self.state.load()
            rec = self.state.addons.get(ref, {})
        channel = channel or rec.get("channel", "stable")
        release = sources.latest(ref, self.client, self.cfg, channel)
        return self.apply(ref, release, progress, channel)

    def apply(self, ref, release, progress=None, channel="stable"):
        name = hashlib.sha1(ref.encode()).hexdigest()[:12]
        zip_path = cache_dir() / "dl" / f"{name}-{time.monotonic_ns()}.zip"
        try:
            try:
                http.download(release.url, zip_path, release.headers, progress)
            except http.HttpError as e:
                raise SourceError(f"Download failed: {e}") from e
            with self.lock:
                try:
                    names = installer.install_zip(zip_path, self.client.addons_dir)
                except installer.InstallError as e:
                    raise SourceError(str(e)) from e
                self.state.load()
                old = self.state.addons.get(ref, {})
                for other, rec in list(self.state.addons.items()):
                    if other == ref:
                        continue
                    left = [d for d in rec.get("dirs", []) if d not in names]
                    if len(left) != len(rec.get("dirs", [])):
                        if left:
                            rec["dirs"] = left
                        else:
                            del self.state.addons[other]
                if old and not old.get("adopted"):
                    for d in old.get("dirs", []):
                        if d not in names:
                            installer.remove(self.client.addons_dir / d)
                main = min(names, key=len)
                fields = toc.read(self.client.addons_dir / main, self.client.flavor)
                hashes, stamps = self._fingerprints(names)
                self.state.addons[ref] = {
                    "name": release.name or toc.clean(fields.get("title", "")) or main,
                    "version": release.version or fields.get("version", ""),
                    "dirs": names,
                    "hashes": hashes,
                    "stamps": stamps,
                    "pinned": bool(old.get("pinned")),
                    "channel": channel,
                    "author": release.author or fields.get("author", ""),
                    "page": release.page or sources.page_of(ref),
                    "time": int(time.time()),
                }
                self.state.save()
                return self.state.addons[ref]
        finally:
            try:
                zip_path.unlink()
            except OSError:
                pass

    def uninstall(self, addon, keep_files=False):
        with self.lock:
            if not keep_files:
                for d in addon.dirs:
                    if "/" in d or d in ("", ".", ".."):
                        continue
                    installer.remove(self.client.addons_dir / d)
            if addon.managed:
                self.state.load()
                self.state.addons.pop(addon.ref, None)
                self.state.save()

    def set_field(self, ref, key, value):
        with self.lock:
            self.state.load()
            if ref in self.state.addons:
                self.state.addons[ref][key] = value
                self.state.save()

    def refs(self):
        with self.lock:
            self.state.load()
            return sorted(self.state.addons)

    def orphans(self):
        wtf = self.client.wtf_dir
        dirs = self.all_dirs()
        out = []
        for pattern in SV_GLOBS:
            for path in wtf.glob(pattern):
                stem = path.name.split(".lua")[0]
                if stem in dirs or stem.startswith("Blizzard_"):
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                out.append({"path": str(path), "addon": stem, "size": size})
        out.sort(key=lambda o: (o["addon"].lower(), o["path"]))
        return out

    def clean_orphans(self):
        allowed = {o["path"] for o in self.orphans()}
        count = 0
        for path in allowed:
            try:
                (self.client.wtf_dir / path).unlink()
                count += 1
            except OSError:
                pass
        return count


def needs_update(addon, release):
    if not release or not addon.managed:
        return False
    return addon.missing or not same_version(addon.version, release.version)


def can_auto_update(addon, release):
    return needs_update(addon, release) and not addon.pinned and (addon.missing or not addon.modified)


def check_one(mgr, addon):
    try:
        if addon.managed:
            return addon, mgr.latest(addon), ""
        adopted, release = mgr.identify(addon)
        if adopted:
            return adopted, release, ""
        return addon, None, ""
    except SourceError as e:
        return addon, None, str(e)
    except Exception as e:
        return addon, None, f"{type(e).__name__}: {e}"


def survey(mgr, workers=6):
    addons = mgr.list()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda a: check_one(mgr, a), addons))


def parse_refs(text):
    out = []
    for token in re.split(r"[\s,]+", text or ""):
        ref = sources.parse_ref(token)
        if ref and ref not in out:
            out.append(ref)
    return out
