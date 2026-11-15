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


SECRET = ("authorization", "x-api-key")


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.request.urlparse(req.full_url), urllib.request.urlparse(newurl)
        if old.scheme == "https" and new.scheme != "https":
            raise urllib.error.HTTPError(newurl, code, "redirect to an insecure address", headers, fp)
        out = super().redirect_request(req, fp, code, msg, headers, newurl)
        if out is not None and old.netloc.lower() != new.netloc.lower():
            for name in [k for k in out.headers if k.lower() in SECRET]:
                del out.headers[name]
        return out


OPENER = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CONTEXT), Redirect)


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
        return OPENER.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, f"HTTP {e.code} from {urllib.request.urlparse(url).netloc}", dict(e.headers)) from e
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise HttpError(0, f"could not reach {urllib.request.urlparse(url).netloc}: {reason}") from e


def final_url(url, timeout=20):
    with _request(url, timeout=timeout) as resp:
        return resp.geturl()


def send_json(url, payload, headers=None, method="POST", timeout=30):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    host = urllib.request.urlparse(url).netloc
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, f"HTTP {e.code} from {host}", dict(e.headers)) from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise HttpError(0, f"could not reach {host}: {getattr(e, 'reason', e)}") from e


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
