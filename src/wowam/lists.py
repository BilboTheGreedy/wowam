import io
import re
import tarfile
import time
import urllib.parse
from pathlib import PurePosixPath

from . import http
from .manager import parse_refs
from .paths import cache_dir
from .sources import SourceError

REPO = "BilboTheGreedy/wowam-lists"
PAGE = f"https://github.com/{REPO}"
ARCHIVE = f"https://codeload.github.com/{REPO}/tar.gz/refs/heads/main"
LIMIT = 200_000
ARCHIVE_LIMIT = 5_000_000
FIELDS = ("name", "by", "for", "about")


def list_url(text):
    t = (text or "").strip()
    if not re.fullmatch(r"https://\S+", t):
        return None
    m = re.match(r"https://gist\.github\.com/([\w-]+)/([0-9a-f]+)", t)
    if m:
        return f"https://gist.githubusercontent.com/{m.group(1)}/{m.group(2)}/raw"
    if re.match(r"https://gist\.githubusercontent\.com/", t):
        return t
    path = t.split("?")[0]
    if not path.lower().endswith(".txt"):
        return None
    m = re.match(r"https://github\.com/([\w.-]+)/([\w.-]+)/(?:blob|raw)/(.+)", path)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return t


def parse(text, slug=""):
    meta = dict.fromkeys(FIELDS, "")
    body = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            m = re.match(r"#\s*(name|by|for|about)\s*:\s*(.*)", line, re.I)
            if m and not meta[m.group(1).lower()]:
                meta[m.group(1).lower()] = m.group(2).strip()[:120]
            continue
        body.append(line)
    return {
        "slug": slug,
        "name": meta["name"] or slug.replace("-", " ").replace("_", " ") or "Addon list",
        "by": meta["by"],
        "game": meta["for"],
        "about": meta["about"],
        "refs": parse_refs(" ".join(body)),
    }


def fetch(url):
    try:
        data = http.get_bytes(url, LIMIT)
    except http.HttpError as e:
        raise SourceError(f"Could not read that list: {e}") from e
    slug = PurePosixPath(urllib.parse.urlparse(url).path).stem
    item = parse(data.decode("utf-8", "replace"), "" if slug == "raw" else slug)
    if not item["refs"]:
        raise SourceError("That link has no addon list in it")
    return item


def unpack(data):
    out = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for member in tf:
            m = re.fullmatch(r"[^/]+/lists/([\w.-]+)\.txt", member.name)
            if not m or not member.isfile() or member.size > LIMIT:
                continue
            item = parse(tf.extractfile(member).read().decode("utf-8", "replace"), m.group(1))
            if item["refs"]:
                out.append(item)
    return sorted(out, key=lambda i: i["name"].lower())


def shared(max_age=3600):
    path = cache_dir() / "lists.tar.gz"
    if not (path.exists() and time.time() - path.stat().st_mtime < max_age):
        try:
            data = http.get_bytes(ARCHIVE, ARCHIVE_LIMIT)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except http.HttpError:
            if not path.exists():
                return []
    try:
        return unpack(path.read_bytes())
    except (OSError, tarfile.TarError, EOFError):
        return []


def template(refs, game=""):
    head = f"# name: My setup\n# by: \n# for: {game}\n# about: \n"
    return head + "\n".join(refs) + "\n"


def share_url(text):
    query = {"filename": "my-setup.txt"}
    if len(text) < 6000:
        query["value"] = text
    return f"{PAGE}/new/main/lists?" + urllib.parse.urlencode(query)
