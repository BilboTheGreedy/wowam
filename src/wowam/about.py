import re
from urllib.parse import quote

from . import http, sources
from .sources import SourceError

LIMIT = 400_000
READMES = ("README.md", "readme.md", "Readme.md", "README.MD", "README", "README.txt")


def bbcode(text):
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"\[code\](.*?)\[/code\]", lambda m: "\n```\n" + m.group(1).strip("\n") + "\n```\n", t, flags=re.I | re.S)
    t = re.sub(r"\[img\]\s*(.*?)\s*\[/img\]", r"![image](\1)", t, flags=re.I | re.S)
    t = re.sub(r'\[url="?([^"\]]+)"?\](.*?)\[/url\]', r"[\2](\1)", t, flags=re.I | re.S)
    t = re.sub(r"\[url\]\s*(.*?)\s*\[/url\]", r"<\1>", t, flags=re.I | re.S)
    t = re.sub(r"\[/?b\]", "**", t, flags=re.I)
    t = re.sub(r"\[/?i\]", "*", t, flags=re.I)
    t = re.sub(r"\s*\[\*\]\s*", "\n- ", t)
    t = re.sub(r"\[/?(?:size|color|font|center|left|right|indent|quote|list|u|s|highlight|email|noparse)(?:=[^\]]*)?\]", "", t, flags=re.I)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return re.sub(r"(?<!\n)\n(?!\n)", "  \n", t).strip()


def _github(ident):
    for name in READMES:
        url = f"https://raw.githubusercontent.com/{ident}/HEAD/{name}"
        try:
            data = http.get_bytes(url, LIMIT)
        except http.HttpError as e:
            if e.status == 404:
                continue
            raise SourceError(f"Could not read the description: {e}") from e
        text = data.decode("utf-8", "replace")
        plain = not name.lower().endswith(".md")
        return {"text": text, "format": "plain" if plain else "markdown", "base": url.rsplit("/", 1)[0] + "/"}
    return {"text": "", "format": "plain", "base": ""}


def fetch(ref, cfg):
    src, ident = ref.split(":", 1)
    out = {"text": "", "format": "markdown", "base": ""}
    try:
        if src == "gh":
            out = _github(ident)
        elif src == "wowi":
            data = http.get_json(f"https://api.mmoui.com/v3/game/WOW/filedetails/{ident}.json", max_age=3600)
            if isinstance(data, list) and data:
                out["text"] = bbcode(data[0].get("UIDescription", ""))
        elif src == "tukui":
            data = http.get_json(f"https://api.tukui.org/v1/addon/{quote(ident)}", max_age=3600)
            shot = data.get("screenshot_url") or ""
            out["text"] = (f"![screenshot]({shot})\n\n" if shot else "") + str(data.get("desc") or data.get("small_desc") or "")
        elif src == "cf":
            mod = sources._cf_mod(ident, cfg)
            out["text"] = str(sources._cf_get(f"/mods/{mod['id']}/description", cfg, 3600) or "")
            out["format"] = "html"
    except http.HttpError as e:
        raise SourceError(f"Could not read the description: {e}") from e
    out["text"] = out["text"].strip()
    return out
