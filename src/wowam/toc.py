import re

SUFFIXES = {
    "mainline": ("mainline",),
    "classic": ("vanilla", "classic"),
    "bcc": ("tbc", "bcc"),
    "wrath": ("wrath", "wotlkc"),
    "titan": ("titan", "wrath"),
    "cata": ("cata",),
    "mists": ("mists",),
    "forever": ("forever",),
}

ALL_SUFFIXES = sorted({s for group in SUFFIXES.values() for s in group})
SUFFIX_RE = re.compile(r"[-_](" + "|".join(ALL_SUFFIXES) + r")$", re.I)
COLOR_RE = re.compile(r"\|c[0-9a-fA-F]{8}|\|r|\|T.*?\|t|\|A.*?\|a")


def strip_suffix(stem):
    return SUFFIX_RE.sub("", stem)


def clean(text):
    return COLOR_RE.sub("", text or "").strip()


def tidy(text):
    t = clean(text)
    m = re.match(r"<([^<>]+)>", t)
    if m:
        t = m.group(1)
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"\s+v?\d+(\.\d+)+\S*$", "", t.strip())
    return " ".join(t.split())


def parse(path):
    fields = {}
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return fields
    for line in text.splitlines():
        m = re.match(r"##\s*([^:]+?)\s*:\s*(.*)$", line.strip())
        if m:
            fields.setdefault(m.group(1).lower(), m.group(2).strip())
    return fields


def find(folder, flavor=""):
    try:
        tocs = [p for p in folder.iterdir() if p.suffix.lower() == ".toc" and p.is_file()]
    except OSError:
        return None
    if not tocs:
        return None
    by_name = {p.stem.lower(): p for p in tocs}
    base = folder.name.lower()
    for suffix in SUFFIXES.get(flavor, ()):
        for sep in ("_", "-"):
            hit = by_name.get(f"{base}{sep}{suffix}")
            if hit:
                return hit
    if base in by_name:
        return by_name[base]
    return sorted(tocs)[0]


def read(folder, flavor=""):
    path = find(folder, flavor)
    return parse(path) if path else {}


def deps(fields):
    out = []
    for key, value in fields.items():
        if key in ("dependencies", "requireddeps") or key.startswith("dep"):
            out.extend(x.strip() for x in value.split(",") if x.strip())
    return out
