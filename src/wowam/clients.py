import hashlib
import re
import string
import sys
from dataclasses import dataclass
from pathlib import Path

FOLDER_PRODUCT = {
    "_retail_": "wow",
    "_ptr_": "wowt",
    "_ptr2_": "wowxptr",
    "_xptr_": "wowxptr",
    "_beta_": "wow_beta",
    "_classic_": "wow_classic",
    "_classic_ptr_": "wow_classic_ptr",
    "_classic_beta_": "wow_classic_beta",
    "_classic_era_": "wow_classic_era",
    "_classic_era_ptr_": "wow_classic_era_ptr",
    "_anniversary_": "wow_anniversary",
    "_forever_": "wowf",
}

FOLDER_LABEL = {
    "_retail_": "Retail",
    "_ptr_": "Retail PTR",
    "_ptr2_": "Retail PTR 2",
    "_xptr_": "Retail PTR",
    "_beta_": "Beta",
    "_classic_": "Classic",
    "_classic_ptr_": "Classic PTR",
    "_classic_beta_": "Classic Beta",
    "_classic_era_": "Classic Era",
    "_classic_era_ptr_": "Classic Era PTR",
    "_anniversary_": "Anniversary",
    "_forever_": "Forever",
}

CLASSIC_BY_MAJOR = {1: "classic", 2: "bcc", 3: "wrath", 4: "cata", 5: "mists"}

WOW_DIRS = (
    "Program Files (x86)/World of Warcraft",
    "Program Files/World of Warcraft",
    "World of Warcraft",
    "Games/World of Warcraft",
)

PREFIX_GLOBS = (
    "Games/*",
    "Games/*/*",
    "Games/Heroic/Prefixes/*",
    "Games/Heroic/Prefixes/default/*",
    ".wine",
    ".local/share/wineprefixes/*",
    ".local/share/bottles/bottles/*",
    ".var/app/com.usebottles.bottles/data/bottles/bottles/*",
    ".steam/steam/steamapps/compatdata/*/pfx",
    ".local/share/Steam/steamapps/compatdata/*/pfx",
    ".local/share/lutris/prefixes/*",
)


@dataclass
class Client:
    path: Path
    folder: str
    product: str
    version: str
    flavor: str
    label: str

    @property
    def addons_dir(self):
        return self.path / "Interface" / "AddOns"

    @property
    def wtf_dir(self):
        return self.path / "WTF"

    @property
    def id(self):
        digest = hashlib.sha1(str(self.path).encode()).hexdigest()[:6]
        return f"{self.folder.strip('_')}-{digest}"

    @property
    def interface(self):
        return interface_of(self.version)

    @property
    def location(self):
        root = self.path.parent
        try:
            parts = root.relative_to(Path.home()).parts
        except ValueError:
            parts = root.parts
        for i, part in enumerate(parts):
            if part == "drive_c" and i > 0:
                return parts[i - 1] if parts[i - 1] != "pfx" else "/".join(parts[max(0, i - 2):i])
        return str(root.parent)


def interface_of(version):
    nums = [int(x) for x in re.findall(r"\d+", version or "")[:3]]
    if len(nums) < 3:
        return 0
    return nums[0] * 10000 + nums[1] * 100 + nums[2]


def flavor_of_version(version):
    nums = [int(x) for x in re.findall(r"\d+", version or "")[:2]]
    if not nums:
        return ""
    major = nums[0]
    minor = nums[1] if len(nums) > 1 else 0
    if major == 1:
        return "forever" if minor >= 50 else "classic"
    if major == 3 and minor >= 80:
        return "titan"
    if major in CLASSIC_BY_MAJOR:
        return CLASSIC_BY_MAJOR[major]
    return "mainline"


def flavor_for(product, folder, version):
    key = product or FOLDER_PRODUCT.get(folder, "")
    if key == "wowf" or folder == "_forever_":
        return "forever"
    if key.startswith("wow_classic_era"):
        return "classic"
    if key.startswith("wow_anniversary"):
        return "bcc"
    if key.startswith("wow_classic_titan"):
        return "titan"
    if key.startswith("wow_classic"):
        nums = re.findall(r"\d+", version or "")
        major = int(nums[0]) if nums else 0
        return CLASSIC_BY_MAJOR.get(major, "mists")
    return "mainline"


def read_build_info(root):
    versions = {}
    try:
        lines = (root / ".build.info").read_text(errors="replace").splitlines()
    except OSError:
        return versions
    if not lines:
        return versions
    header = [h.split("!")[0] for h in lines[0].split("|")]
    if "Product" not in header or "Version" not in header:
        return versions
    pi, vi = header.index("Product"), header.index("Version")
    for line in lines[1:]:
        cols = line.split("|")
        if len(cols) > max(pi, vi):
            versions[cols[pi]] = cols[vi]
    return versions


def read_product(client_dir):
    try:
        lines = (client_dir / ".flavor.info").read_text(errors="replace").splitlines()
    except OSError:
        return ""
    return lines[1].strip() if len(lines) > 1 else ""


def is_client_dir(path):
    if not path.is_dir() or not re.fullmatch(r"_\w+_", path.name):
        return False
    if (path / ".flavor.info").exists():
        return True
    try:
        for p in path.iterdir():
            name = p.name.lower()
            if name.startswith("wow") and name.endswith(".exe"):
                return True
            if name.startswith("world of warcraft") and name.endswith(".app"):
                return True
    except OSError:
        pass
    return False


def clients_in(root):
    found = []
    try:
        children = sorted(root.iterdir())
    except OSError:
        return found
    versions = read_build_info(root)
    for child in children:
        if not is_client_dir(child):
            continue
        product = read_product(child) or FOLDER_PRODUCT.get(child.name, "")
        version = versions.get(product, "")
        label = FOLDER_LABEL.get(child.name, child.name.strip("_").replace("_", " ").title())
        found.append(Client(child, child.name, product, version, flavor_for(product, child.name, version), label))
    return found


def lutris_prefixes(home):
    out = []
    for base in (home / ".config/lutris/games", home / ".local/share/lutris/games"):
        try:
            files = list(base.glob("*.yml"))
        except OSError:
            continue
        for f in files:
            try:
                text = f.read_text(errors="replace")
            except OSError:
                continue
            for m in re.finditer(r"^\s*prefix:\s*['\"]?(.+?)['\"]?\s*$", text, re.M):
                out.append(Path(m.group(1)).expanduser())
    return out


def candidate_roots(home):
    prefixes = []
    for pattern in PREFIX_GLOBS:
        try:
            prefixes.extend(home.glob(pattern))
        except OSError:
            pass
    prefixes.extend(lutris_prefixes(home))
    for prefix in prefixes:
        drive = prefix / "drive_c"
        if not drive.is_dir():
            continue
        for sub in WOW_DIRS:
            yield drive / sub


def registry_roots():
    out = []
    try:
        import winreg
    except ImportError:
        return out
    for sub in (
        r"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft",
        r"SOFTWARE\Blizzard Entertainment\World of Warcraft",
    ):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as key:
                value, _ = winreg.QueryValueEx(key, "InstallPath")
        except OSError:
            continue
        if value:
            out.extend(roots_for(str(value).rstrip("\\/")))
    return out


def native_roots():
    out = []
    if sys.platform == "win32":
        out.extend(registry_roots())
        for letter in string.ascii_uppercase[2:]:
            drive = Path(f"{letter}:\\")
            if not drive.exists():
                continue
            for sub in WOW_DIRS:
                out.append(drive / sub)
    elif sys.platform == "darwin":
        out.append(Path("/Applications/World of Warcraft"))
        out.append(Path.home() / "Applications" / "World of Warcraft")
    return out


def roots_for(path):
    path = Path(path).expanduser()
    if is_client_dir(path):
        return [path.parent]
    out = [path]
    for sub in WOW_DIRS:
        out.append(path / "drive_c" / sub)
        out.append(path / sub)
    return out


def discover(extra_paths=(), home=None):
    native = home is None
    home = Path(home) if home else Path.home()
    seen = set()
    clients = []
    roots = list(candidate_roots(home))
    if native:
        roots.extend(native_roots())
    for extra in extra_paths:
        roots.extend(roots_for(extra))
    for root in roots:
        try:
            real = root.resolve()
        except OSError:
            continue
        if real in seen or not real.is_dir():
            continue
        seen.add(real)
        clients.extend(clients_in(real))
    order = list(FOLDER_LABEL)
    clients.sort(key=lambda c: (str(c.path.parent), order.index(c.folder) if c.folder in order else 99))
    return clients
