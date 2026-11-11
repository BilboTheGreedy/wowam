import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.request

from . import __version__
from .paths import cache_dir

UA = f"wowam/{__version__}"


CA_FILES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/cert.pem",
    "/etc/ssl/ca-bundle.pem",
)


def _context():
    ctx = ssl.create_default_context()
    for path in CA_FILES:
        if os.path.isfile(path):
            try:
                ctx.load_verify_locations(cafile=path)
            except (OSError, ssl.SSLError):
                pass
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    except (ImportError, OSError, ssl.SSLError):
        pass
    return ctx


CONTEXT = _context()


class HttpError(Exception):
    def __init__(self, status, message, headers=None):
        super().__init__(message)
        self.status = status
        self.headers = headers or {}


def _cache_path(url, kind):
    name = hashlib.sha1(url.encode()).hexdigest()
    return cache_dir() / kind / name


def _request(url, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=CONTEXT)
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, f"HTTP {e.code} from {urllib.request.urlparse(url).netloc}", dict(e.headers)) from e
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise HttpError(0, f"could not reach {urllib.request.urlparse(url).netloc}: {reason}") from e


def final_url(url, timeout=20):
    with _request(url, timeout=timeout) as resp:
        return resp.geturl()


def get_bytes(url, limit, headers=None, timeout=30):
    with _request(url, headers, timeout=timeout) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise HttpError(0, f"{urllib.request.urlparse(url).netloc} sent too much data")
    return data


def get_json(url, headers=None, etag=False, max_age=0, timeout=30):
    body_path = _cache_path(url, "http")
    meta_path = body_path.with_suffix(".meta")
    if max_age and body_path.exists() and time.time() - body_path.stat().st_mtime < max_age:
        try:
            return json.loads(body_path.read_bytes())
        except ValueError:
            pass
    headers = dict(headers or {})
    if etag and body_path.exists() and meta_path.exists():
        headers["If-None-Match"] = meta_path.read_text().strip()
    try:
        with _request(url, headers, timeout=timeout) as resp:
            body = resp.read()
            tag = resp.headers.get("ETag", "")
    except HttpError as e:
        if e.status == 304 or (etag and e.status in (403, 429) and body_path.exists()):
            try:
                return json.loads(body_path.read_bytes())
            except (OSError, ValueError):
                pass
        raise
    try:
        parsed = json.loads(body)
    except ValueError as e:
        raise HttpError(0, f"bad response from {urllib.request.urlparse(url).netloc}") from e
    if etag or max_age:
        body_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = body_path.with_suffix(f".{os.getpid()}.{time.monotonic_ns()}.tmp")
        tmp.write_bytes(body)
        os.replace(tmp, body_path)
        if tag:
            meta_path.write_text(tag)
    return parsed


def download(url, dest, headers=None, progress=None, timeout=60):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _request(url, headers, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total)
    return dest
