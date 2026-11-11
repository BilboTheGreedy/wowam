import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, quote_plus

from . import http
from .clients import flavor_of_version
from .http import HttpError

LABELS = {"gh": "GitHub", "wowi": "WoWInterface", "tukui": "Tukui", "wago": "Wago", "cf": "CurseForge"}
ALIASES = {"github": "gh", "wa": "wago", "wowinterface": "wowi", "curse": "cf", "curseforge": "cf"}

CF_API = "https://api.curseforge.com/v1"
CF_TYPE = {"mainline": 517, "classic": 67408, "bcc": 73246, "wrath": 73713, "titan": 73713, "cata": 77522, "mists": 79434}

WAGO_GAME = {
    "mainline": "retail",
    "classic": "classic",
    "bcc": "bc",
    "wrath": "wotlk",
    "titan": "wotlk",
    "cata": "cata",
    "mists": "mop",
    "forever": "forever",
}

NAME_HINTS = {
    "mainline": ("mainline", "retail"),
    "classic": ("classic", "vanilla", "era"),
    "bcc": ("bcc", "tbc"),
    "wrath": ("wrath", "wotlk"),
    "titan": ("titan",),
    "cata": ("cata",),
    "mists": ("mists", "mop"),
    "forever": ("forever",),
}

_memo = {}
_memo_lock = threading.Lock()


class SourceError(Exception):
    pass


@dataclass
class Release:
    version: str
    url: str
    name: str = ""
    author: str = ""
    page: str = ""
    headers: dict = field(default_factory=dict)
    notes: str = ""


def parse_ref(text):
    t = (text or "").strip().strip("\"'<>")
    if not t:
        return None
    m = re.match(r"wago-app://addons/([\w.-]+)", t, re.I)
    if m:
        return f"wago:{m.group(1)}"
    m = re.match(r"(?i)^(gh|github|wowi|wowinterface|tukui|wago|wa|cf|curse|curseforge):(.+)$", t)
    if m and not m.group(2).startswith("//"):
        src = m.group(1).lower()
        src = ALIASES.get(src, src)
        ident = m.group(2).strip().strip("/")
        if src == "gh":
            if not re.fullmatch(r"[\w.-]+/[\w.-]+", ident):
                return None
        elif src == "wowi":
            if not ident.isdigit():
                return None
        elif src in ("tukui", "cf"):
            ident = ident.lower()
        if not re.fullmatch(r"[\w./-]+", ident):
            return None
        return f"{src}:{ident}"
    m = re.search(r"github\.com/([\w.-]+)/([\w.-]+)", t, re.I)
    if m:
        repo = m.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return f"gh:{m.group(1)}/{repo}"
    m = re.search(r"wowinterface\.com/downloads/(?:info|download|fileinfo\.php\?id=)(\d+)", t, re.I)
    if m:
        return f"wowi:{m.group(1)}"
    m = re.search(r"addons\.wago\.io/addons/([\w.-]+)", t, re.I)
    if m:
        return f"wago:{m.group(1)}"
    m = re.search(r"curseforge\.com/wow/addons/([\w-]+)", t, re.I)
    if m:
        return f"cf:{m.group(1).lower()}"
    m = re.search(r"tukui\.org/(elvui|tukui)\b", t, re.I)
    if m:
        return f"tukui:{m.group(1).lower()}"
    if t.lower() in ("elvui", "tukui"):
        return f"tukui:{t.lower()}"
    if re.fullmatch(r"[\w.-]+/[\w.-]+", t):
        return f"gh:{t}"
    return None


def split_ref(ref):
    src, _, ident = ref.partition(":")
    return src, ident


def label(ref):
    return LABELS.get(split_ref(ref or "")[0], "")


def page_of(ref):
    src, ident = split_ref(ref)
    if src == "gh":
        return f"https://github.com/{ident}"
    if src == "wowi":
        return f"https://www.wowinterface.com/downloads/info{ident}"
    if src == "wago":
        return f"https://addons.wago.io/addons/{ident}"
    if src == "tukui":
        return f"https://tukui.org/{ident}"
    if src == "cf":
        if ident.isdigit():
            return f"https://www.curseforge.com/projects/{ident}"
        return f"https://www.curseforge.com/wow/addons/{ident}"
    return ""


def gh_token(cfg):
    saved = cfg.get("github_token")
    if saved:
        return saved
    with _memo_lock:
        if "cli" not in _memo:
            _memo["cli"] = _cli_token()
        return _memo["cli"]


def _cli_token():
    exe = shutil.which("gh")
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _gh_headers(cfg):
    headers = {"Accept": "application/vnd.github+json"}
    token = gh_token(cfg)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _gh_error(e, ident):
    if e.status in (403, 429):
        return SourceError("GitHub rate limit reached. Add a GitHub token in Settings or try again in an hour.")
    if e.status == 401:
        return SourceError("GitHub rejected the token set in Settings.")
    if e.status == 404:
        return SourceError(f"GitHub project {ident} was not found.")
    return SourceError(str(e))


def _gh_pick(release, client):
    assets = release.get("assets") or []
    zips = [a for a in assets if a["name"].lower().endswith(".zip")]
    manifest = next((a for a in assets if a["name"] == "release.json"), None)
    if manifest:
        try:
            data = http.get_json(manifest["browser_download_url"], max_age=10**9)
        except HttpError:
            data = None
        if data:
            for entry in data.get("releases", []):
                if entry.get("nolib"):
                    continue
                flavors = {m.get("flavor") for m in entry.get("metadata", [])}
                if client.flavor in flavors:
                    hit = next((a for a in zips if a["name"] == entry.get("filename")), None)
                    if hit:
                        return hit["browser_download_url"]
            return None
    zips = [a for a in zips if "nolib" not in a["name"].lower()]
    if not zips:
        if not assets and release.get("zipball_url"):
            return release["zipball_url"]
        return None
    best, best_score = None, -99
    for a in zips:
        name = a["name"].lower()
        score = 0
        for flavor, hints in NAME_HINTS.items():
            if any(re.search(rf"(?<![a-z]){h}(?![a-z])", name) for h in hints):
                score += 2 if flavor == client.flavor else -1
        if score > best_score:
            best, best_score = a, score
    if best_score < 0:
        return None
    return best["browser_download_url"]


def _gh_branch(ident, cfg):
    try:
        commits = http.get_json(f"https://api.github.com/repos/{ident}/commits?per_page=1", _gh_headers(cfg), etag=True)
    except HttpError as e:
        if e.status == 409:
            raise SourceError(f"{ident} is empty on GitHub.") from e
        raise _gh_error(e, ident) from e
    if not isinstance(commits, list) or not commits:
        raise SourceError(f"{ident} is empty on GitHub.")
    sha = commits[0]["sha"]
    info = commits[0].get("commit") or {}
    day = ((info.get("committer") or {}).get("date") or "")[:10]
    return Release(
        version=f"{day}-{sha[:7]}" if day else sha[:7],
        url=f"https://api.github.com/repos/{ident}/zipball/{sha}",
        name="",
        author=ident.split("/")[0],
        page=f"https://github.com/{ident}",
        headers=_gh_headers(cfg),
        notes=(info.get("message") or "").strip()[:8000],
    )


def _gh_latest(ident, client, cfg, channel):
    try:
        releases = http.get_json(
            f"https://api.github.com/repos/{ident}/releases?per_page=15", _gh_headers(cfg), etag=True
        )
    except HttpError as e:
        raise _gh_error(e, ident) from e
    if not isinstance(releases, list) or not releases:
        return _gh_branch(ident, cfg)
    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and channel == "stable":
            continue
        url = _gh_pick(release, client)
        if url:
            headers = _gh_headers(cfg) if "api.github.com" in url else {}
            return Release(
                version=release.get("tag_name") or release.get("name") or "",
                url=url,
                name="",
                author=ident.split("/")[0],
                page=f"https://github.com/{ident}",
                headers=headers,
                notes=(release.get("body") or "").strip()[:8000],
            )
    raise SourceError(f"{ident} has no download for {client.label}.")


def _wowi_latest(ident, client, cfg, channel):
    try:
        data = http.get_json(f"https://api.mmoui.com/v3/game/WOW/filedetails/{ident}.json")
    except HttpError as e:
        if e.status == 404:
            raise SourceError(f"WoWInterface addon {ident} was not found.") from e
        raise SourceError(str(e)) from e
    if not isinstance(data, list) or not data:
        raise SourceError(f"WoWInterface addon {ident} was not found.")
    item = data[0]
    return Release(
        version=str(item.get("UIVersion", "")),
        url=item["UIDownload"],
        name=item.get("UIName", ""),
        author=item.get("UIAuthorName", ""),
        page=f"https://www.wowinterface.com/downloads/info{ident}",
        notes=re.sub(r"\[/?\w+[^\]]*\]", "", str(item.get("UIChangeLog") or "")).strip()[:8000],
    )


def wowi_index():
    with _memo_lock:
        if "wowi" in _memo:
            return _memo["wowi"]
        try:
            data = http.get_json("https://api.mmoui.com/v3/game/WOW/filelist.json", max_age=43200, timeout=120)
        except HttpError as e:
            raise SourceError(str(e)) from e
        if not isinstance(data, list):
            raise SourceError("bad response from WoWInterface")
        _memo["wowi"] = data
        return data


def wowi_by_dir(folder):
    hits = [x for x in wowi_index() if folder in (x.get("UIDir") or [])]
    hits.sort(key=lambda x: int(x.get("UIDownloadTotal") or 0), reverse=True)
    return hits


def _tukui_latest(ident, client, cfg, channel):
    try:
        data = http.get_json(f"https://api.tukui.org/v1/addon/{quote(ident)}")
    except HttpError as e:
        if e.status == 404:
            raise SourceError(f"Tukui addon {ident} was not found.") from e
        raise SourceError(str(e)) from e
    return Release(
        version=str(data.get("version", "")),
        url=data["url"],
        name=data.get("name", ""),
        author=data.get("author", ""),
        page=data.get("web_url", ""),
    )


def _wago_headers(cfg):
    key = cfg.get("wago_key")
    if not key:
        raise SourceError("Wago Addons needs an API key. Add one in Settings.")
    return {"Authorization": f"Bearer {key}"}


def _wago_error(e):
    if e.status == 401:
        return SourceError("Wago Addons rejected the API key set in Settings.")
    if e.status in (403, 423):
        return SourceError("The Wago Addons API key is expired or blocked.")
    if e.status == 404:
        return SourceError("This addon was not found on Wago Addons.")
    return SourceError(str(e))


def _wago_latest(ident, client, cfg, channel):
    headers = _wago_headers(cfg)
    game = WAGO_GAME.get(client.flavor, "retail")
    try:
        data = http.get_json(
            f"https://addons.wago.io/api/external/addons/{quote(ident)}?game_version={game}", headers
        )
    except HttpError as e:
        raise _wago_error(e) from e
    recent = data.get("recent_release") or data.get("recent_releases") or {}
    wanted = ("stable",) if channel == "stable" else ("stable", "beta", "alpha")
    picks = [recent[c] for c in wanted if c in recent]
    if not picks:
        picks = [recent[c] for c in ("stable", "beta", "alpha") if c in recent]
    if not picks:
        raise SourceError(f"No Wago release for {client.label}.")
    release = max(picks, key=lambda r: r.get("created_at", ""))
    authors = data.get("authors") or ""
    if isinstance(authors, list):
        authors = ", ".join(str(a) for a in authors)
    return Release(
        version=str(release.get("label", "")),
        url=release.get("download_link") or release.get("link"),
        name=data.get("display_name") or data.get("name") or "",
        author=authors,
        page=data.get("website_url", ""),
        headers=headers,
    )


def cf_key(cfg):
    saved = cfg.get("curseforge_key")
    if saved:
        return saved
    with _memo_lock:
        if "cf" not in _memo:
            try:
                _memo["cf"] = (Path(__file__).parent / "data" / "cf.key").read_text().strip()
            except OSError:
                _memo["cf"] = ""
        return _memo["cf"]


def _cf_headers(cfg):
    key = cf_key(cfg)
    if not key:
        raise SourceError("CurseForge needs an API key. Add one in Settings.")
    return {"x-api-key": key, "Accept": "application/json"}


def _cf_error(e):
    if e.status in (401, 403):
        return SourceError("CurseForge rejected the API key set in Settings.")
    if e.status == 404:
        return SourceError("This addon was not found on CurseForge.")
    return SourceError(str(e))


def _cf_get(path, cfg, max_age=0):
    try:
        data = http.get_json(CF_API + path, _cf_headers(cfg), max_age=max_age)
    except HttpError as e:
        raise _cf_error(e) from e
    return data.get("data") if isinstance(data, dict) else None


def _cf_mod(ident, cfg):
    if ident.isdigit():
        mod = _cf_get(f"/mods/{ident}", cfg, 3600)
    else:
        hits = _cf_get(f"/mods/search?gameId=1&slug={quote(ident)}", cfg, 3600) or []
        mod = hits[0] if hits else None
    if not isinstance(mod, dict) or not mod.get("id"):
        raise SourceError("This addon was not found on CurseForge.")
    return mod


def _cf_author(mod):
    return ", ".join(a.get("name", "") for a in mod.get("authors") or [] if a.get("name"))


def _cf_latest(ident, client, cfg, channel):
    mod = _cf_mod(ident, cfg)
    kind = CF_TYPE.get(client.flavor)
    path = f"/mods/{mod['id']}/files?pageSize=30" + (f"&gameVersionTypeId={kind}" if kind else "")
    files = [f for f in _cf_get(path, cfg) or [] if f.get("isAvailable", True)]
    wanted = (1,) if channel == "stable" else (1, 2, 3)
    picks = [f for f in files if f.get("releaseType") in wanted] or files
    if not picks:
        raise SourceError(f"No CurseForge file for {client.label}.")
    newest = max(picks, key=lambda f: f.get("fileDate", ""))
    if not newest.get("downloadUrl"):
        raise SourceError("The author only allows this addon to be downloaded with the CurseForge app.")
    return Release(
        version=str(newest.get("displayName") or newest.get("fileName") or ""),
        url=newest["downloadUrl"],
        name=mod.get("name", ""),
        author=_cf_author(mod),
        page=(mod.get("links") or {}).get("websiteUrl", ""),
    )


_LATEST = {"gh": _gh_latest, "wowi": _wowi_latest, "tukui": _tukui_latest, "wago": _wago_latest, "cf": _cf_latest}


def latest(ref, client, cfg, channel="stable"):
    src, ident = split_ref(ref)
    fn = _LATEST.get(src)
    if not fn or not ident:
        raise SourceError(f"Unknown source: {ref}")
    release = fn(ident, client, cfg, channel)
    if not release.url:
        raise SourceError("The source did not give a download link.")
    return release


def _listed(flavors, client):
    if not flavors:
        return "unknown"
    return "yes" if client.flavor in flavors else "no"


def _result(ref, name, author="", version="", downloads=0, summary="", listed="unknown", page="", dirs=()):
    return {
        "ref": ref,
        "name": name,
        "author": author,
        "version": version,
        "downloads": downloads,
        "summary": summary,
        "listed": listed,
        "page": page or page_of(ref),
        "source": label(ref),
        "dirs": list(dirs),
    }


def _search_wowi(words, client):
    out = []
    for x in wowi_index():
        hay = f"{x.get('UIName', '')} {x.get('UIAuthorName', '')}".lower()
        if not all(w in hay for w in words):
            continue
        compat = x.get("UICompatibility") or []
        flavors = {flavor_of_version(c.get("version", "")) for c in compat}
        out.append(
            _result(
                f"wowi:{x['UID']}",
                x.get("UIName", ""),
                x.get("UIAuthorName", ""),
                str(x.get("UIVersion", "")),
                int(x.get("UIDownloadMonthly") or 0),
                "",
                _listed(flavors, client),
                x.get("UIFileInfoURL", ""),
                x.get("UIDir") or (),
            )
        )
    return out


def _search_tukui(words, client):
    try:
        data = http.get_json("https://api.tukui.org/v1/addons", max_age=3600)
    except HttpError:
        return []
    out = []
    for x in data if isinstance(data, list) else []:
        hay = f"{x.get('name', '')} {x.get('author', '')}".lower()
        if not all(w in hay for w in words):
            continue
        flavors = {flavor_of_version(p) for p in x.get("patch") or []}
        out.append(
            _result(
                f"tukui:{x.get('slug', '')}",
                x.get("name", ""),
                x.get("author", ""),
                str(x.get("version", "")),
                10**9,
                x.get("small_desc", ""),
                _listed(flavors, client),
                x.get("web_url", ""),
                x.get("directories") or (),
            )
        )
    return out


def _search_wago(query, client, cfg):
    if not cfg.get("wago_key"):
        return []
    game = WAGO_GAME.get(client.flavor, "retail")
    try:
        data = http.get_json(
            f"https://addons.wago.io/api/external/addons/_search?query={quote_plus(query)}&game_version={game}",
            _wago_headers(cfg),
        )
    except HttpError:
        return []
    out = []
    for x in data.get("data", []) if isinstance(data, dict) else []:
        ref = parse_ref(x.get("website_url", "")) or (f"wago:{x['slug']}" if x.get("slug") else None)
        if not ref:
            continue
        authors = x.get("authors") or ""
        if isinstance(authors, list):
            authors = ", ".join(str(a) for a in authors)
        out.append(
            _result(
                ref,
                x.get("display_name") or x.get("name") or ref,
                authors,
                "",
                int(x.get("download_count") or 0),
                x.get("summary", ""),
                "yes",
                x.get("website_url", ""),
            )
        )
    return out


def _search_cf(query, client, cfg):
    if not cf_key(cfg):
        return []
    kind = CF_TYPE.get(client.flavor)
    path = f"/mods/search?gameId=1&searchFilter={quote_plus(query)}&sortField=6&sortOrder=desc&pageSize=20"
    try:
        hits = _cf_get(path + (f"&gameVersionTypeId={kind}" if kind else ""), cfg, 900) or []
    except SourceError:
        return []
    out = []
    for mod in hits:
        if not mod.get("id"):
            continue
        out.append(
            _result(
                f"cf:{mod['id']}",
                mod.get("name", ""),
                _cf_author(mod),
                "",
                int(mod.get("downloadCount") or 0),
                mod.get("summary", ""),
                "yes" if kind else "unknown",
                (mod.get("links") or {}).get("websiteUrl", ""),
            )
        )
    return out


def _gh_manifest(full_name):
    try:
        data = http.get_json(f"https://github.com/{full_name}/releases/latest/download/release.json", max_age=3600)
    except HttpError:
        return None
    return data if isinstance(data, dict) else None


def _search_github(query, client, cfg, top=8):
    url = (
        "https://api.github.com/search/repositories?q="
        + quote_plus(f"{query} in:name language:lua")
        + f"&sort=stars&per_page={top}"
    )
    try:
        data = http.get_json(url, _gh_headers(cfg), max_age=900)
    except HttpError:
        return []
    repos = [r for r in (data.get("items") or []) if r.get("full_name")][:top]
    if not repos:
        return []
    with ThreadPoolExecutor(max_workers=top) as pool:
        manifests = list(pool.map(lambda r: _gh_manifest(r["full_name"]), repos))
    out = []
    for repo, manifest in zip(repos, manifests):
        if not manifest:
            continue
        entries = [e for e in manifest.get("releases", []) if not e.get("nolib")]
        flavors = {m.get("flavor") for e in entries for m in e.get("metadata", [])}
        version = next((str(e.get("version", "")) for e in entries), "")
        out.append(
            _result(
                f"gh:{repo['full_name']}",
                repo.get("name", ""),
                (repo.get("owner") or {}).get("login", ""),
                version,
                int(repo.get("stargazers_count") or 0),
                repo.get("description") or "",
                _listed(flavors, client),
                repo.get("html_url", ""),
            )
        )
    return out


def search(query, client, cfg, limit=60):
    query = (query or "").strip()
    if not query:
        return []
    direct = parse_ref(query) if re.search(r"[:/]", query) else None
    if direct:
        release = latest(direct, client, cfg)
        name = release.name or split_ref(direct)[1].split("/")[-1]
        return [_result(direct, name, release.author, release.version, 0, "", "direct", release.page)]
    words = query.lower().split()
    results = (
        _search_tukui(words, client)
        + _search_github(query, client, cfg)
        + _search_wago(query, client, cfg)
        + _search_cf(query, client, cfg)
        + _search_wowi(words, client)
    )
    exact = query.lower()
    rank = {"yes": 0, "direct": 0, "unknown": 1, "no": 2}
    results.sort(key=lambda r: (r["name"].lower() != exact, rank.get(r["listed"], 1), -r["downloads"]))
    return results[:limit]
