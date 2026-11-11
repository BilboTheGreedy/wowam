import argparse
import os
import sys

from . import __version__, auras, backup, desktop, lists, selfupdate
from .clients import discover
from .config import Config
from .manager import Manager, can_auto_update, needs_update, parse_refs, survey
from .sources import SourceError, label, parse_ref


def find_clients(cfg):
    return discover(cfg.get("extra_paths"))


def pick(clients, name, cfg):
    if not clients:
        sys.exit("no WoW installs found, add one with: wowam add-path <folder>")
    if not name:
        last = cfg.get("last_client")
        return next((c for c in clients if c.id == last), clients[0])
    want = name.strip("_").lower()
    for c in clients:
        if c.id == name or c.folder.strip("_").lower() == want or c.label.lower() == name.lower():
            return c
    sys.exit(f"no install called {name}")


def targets(args, cfg):
    clients = find_clients(cfg)
    if getattr(args, "all", False):
        return clients
    return [pick(clients, args.client, cfg)]


def cmd_clients(args, cfg):
    for c in find_clients(cfg):
        print(f"{c.folder.strip('_'):16} {c.label:16} {c.version or '-':16} {c.path}")


def cmd_status(args, cfg):
    for c in targets(args, cfg):
        print(f"{c.label} ({c.path})")
        for addon, release, error in survey(Manager(c, cfg)):
            if error:
                state = f"error: {error}"
            elif not addon.managed:
                state = "unknown source"
            elif needs_update(addon, release):
                state = f"update {release.version}"
            else:
                state = "ok"
            flags = "".join(f for f, on in (("P", addon.pinned), ("M", addon.modified)) if on)
            print(f"  {addon.name[:34]:34} {addon.version[:22]:22} {label(addon.ref):13} {flags:2} {state}")


def cmd_install(args, cfg):
    c = pick(find_clients(cfg), args.client, cfg)
    mgr = Manager(c, cfg)
    failed = 0
    for text in args.refs:
        if text.lower().endswith(".zip") and os.path.isfile(text):
            try:
                rec = mgr.install_file(text)
                print(f"installed {rec['name']} {rec['version']}")
            except SourceError as e:
                print(f"{text}: {e}")
                failed += 1
            continue
        ref = parse_ref(text)
        if not ref:
            print(f"{text}: not a known link")
            failed += 1
            continue
        try:
            rec = mgr.install(ref)
            print(f"installed {rec['name']} {rec['version']}")
        except SourceError as e:
            print(f"{text}: {e}")
            failed += 1
    return 1 if failed else 0


def update_client(c, cfg, names=(), force=False, quiet=False):
    mgr = Manager(c, cfg)
    wanted = [n.lower() for n in names]
    todo = []
    errors = []
    for addon, release, error in survey(mgr):
        if wanted and addon.name.lower() not in wanted and addon.ref.lower() not in wanted:
            continue
        if error:
            errors.append(f"{addon.name}: {error}")
        elif force and addon.managed and release and (wanted or needs_update(addon, release)):
            todo.append((addon, release))
        elif can_auto_update(addon, release):
            todo.append((addon, release))
    done = []
    if todo and cfg.get("backup_on_update"):
        backup.create(c, cfg.get("backup_keep"))
    for addon, release in todo:
        try:
            rec = mgr.apply(addon.ref, release, channel=addon.channel)
            done.append(f"{rec['name']} {rec['version']}")
        except SourceError as e:
            errors.append(f"{addon.name}: {e}")
    if not quiet:
        for line in done:
            print(f"updated {line}")
        for line in errors:
            print(f"failed {line}")
        if not done and not errors:
            print(f"{c.label}: nothing to update")
    return done, errors


def cmd_update(args, cfg):
    failed = False
    for c in targets(args, cfg):
        _, errors = update_client(c, cfg, args.names, args.force)
        failed = failed or bool(errors)
    return 1 if failed else 0


def cmd_auto(args, cfg):
    lines = []
    problems = 0
    for c in find_clients(cfg):
        done, errors = update_client(c, cfg, quiet=True)
        problems += len(errors)
        if cfg.get("aura_updates"):
            try:
                found = auras.sync(c)
            except OSError:
                found = []
            if found:
                done = done + [f"{len(found)} WeakAuras ready in game"]
        if done:
            lines.append(f"{c.label}: " + ", ".join(done))
        for e in errors:
            print(f"{c.label}: {e}")
    for line in lines:
        print(line)
    if lines:
        desktop.notify("Addons updated", "\n".join(lines))
    elif problems:
        desktop.notify("Addon update problems", f"{problems} addon(s) could not be checked")
    return 0


def find_addon(mgr, name):
    low = name.lower()
    for a in mgr.list():
        if low in (a.name.lower(), a.ref.lower(), a.key.lower()) or low in (d.lower() for d in a.dirs[:1]):
            return a
    sys.exit(f"no addon called {name}")


def cmd_remove(args, cfg):
    mgr = Manager(pick(find_clients(cfg), args.client, cfg), cfg)
    for name in args.names:
        addon = find_addon(mgr, name)
        mgr.uninstall(addon, keep_files=args.keep)
        print(f"removed {addon.name}")


def cmd_pin(args, cfg):
    mgr = Manager(pick(find_clients(cfg), args.client, cfg), cfg)
    for name in args.names:
        addon = find_addon(mgr, name)
        if not addon.managed:
            print(f"{addon.name}: unknown source")
            continue
        mgr.set_field(addon.ref, "pinned", args.cmd == "pin")
        print(f"{'pinned' if args.cmd == 'pin' else 'unpinned'} {addon.name}")


def cmd_link(args, cfg):
    mgr = Manager(pick(find_clients(cfg), args.client, cfg), cfg)
    addon = find_addon(mgr, args.name)
    ref = parse_ref(args.ref)
    if not ref:
        sys.exit("not a known link")
    try:
        mgr.link(addon, ref)
    except SourceError as e:
        sys.exit(str(e))
    print(f"linked {addon.name} to {ref}")


def cmd_backup(args, cfg):
    for c in targets(args, cfg):
        path = backup.create(c, cfg.get("backup_keep"))
        print(path if path else f"{c.label}: nothing to back up")


def cmd_export(args, cfg):
    mgr = Manager(pick(find_clients(cfg), args.client, cfg), cfg)
    print(" ".join(mgr.refs()))


def cmd_import(args, cfg):
    text = " ".join(args.refs)
    url = lists.list_url(text)
    args.refs = lists.fetch(url)["refs"] if url else parse_refs(text)
    return cmd_install(args, cfg)


def cmd_add_path(args, cfg):
    paths = list(cfg.get("extra_paths"))
    if args.path not in paths:
        paths.append(args.path)
        cfg.set("extra_paths", paths)
    cmd_clients(args, cfg)


def cmd_desktop(args, cfg):
    if args.action == "install":
        desktop.install_launcher()
    else:
        desktop.remove_launcher()


def cmd_timer(args, cfg):
    if args.action == "on":
        if not desktop.enable_timer():
            sys.exit("could not enable the timer")
    else:
        desktop.disable_timer()


def cmd_self_update(args, cfg):
    info = selfupdate.check()
    if not info:
        print(f"wowam {__version__} is the newest version")
        return 0
    if not info["url"]:
        print(f"wowam {info['version']} is out: {info['page']}")
        return 0
    try:
        selfupdate.install(info, relaunch=False)
    except selfupdate.UpdateError as e:
        sys.exit(str(e))
    print(f"updated to wowam {info['version']}")
    return 0


def cmd_gui(args, cfg):
    from .gui.app import run

    return run(getattr(args, "uri", "") or "", hidden=bool(getattr(args, "hidden", False)))


def build_parser():
    p = argparse.ArgumentParser(prog="wowam", description="World of Warcraft addon manager")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")

    def add(name, fn, help_text, client=True, every=False):
        sp = sub.add_parser(name, help=help_text)
        sp.set_defaults(fn=fn)
        if client:
            sp.add_argument("-c", "--client", help="install to use, for example retail")
        if every:
            sp.add_argument("-a", "--all", action="store_true", help="every install")
        return sp

    sp = add("gui", cmd_gui, "open the window", client=False)
    sp.add_argument("uri", nargs="?")
    sp.add_argument("--hidden", action="store_true", help="start in the tray when the tray icon is on")
    add("clients", cmd_clients, "list WoW installs", client=False)
    add("status", cmd_status, "show addons and available updates", every=True)
    add("install", cmd_install, "install addons from links").add_argument("refs", nargs="+")
    sp = add("update", cmd_update, "update addons", every=True)
    sp.add_argument("names", nargs="*")
    sp.add_argument("-f", "--force", action="store_true", help="also update pinned or modified addons")
    sp = add("remove", cmd_remove, "remove addons")
    sp.add_argument("names", nargs="+")
    sp.add_argument("-k", "--keep", action="store_true", help="keep the files")
    add("pin", cmd_pin, "stop updating an addon").add_argument("names", nargs="+")
    add("unpin", cmd_pin, "update an addon again").add_argument("names", nargs="+")
    sp = add("link", cmd_link, "tell wowam where an addon comes from")
    sp.add_argument("name")
    sp.add_argument("ref")
    add("backup", cmd_backup, "back up settings (WTF)", every=True)
    add("export", cmd_export, "print the addon list")
    add("import", cmd_import, "install an exported addon list").add_argument("refs", nargs="+")
    add("auto", cmd_auto, "update everything quietly", client=False)
    add("self-update", cmd_self_update, "update wowam itself", client=False)
    add("add-path", cmd_add_path, "add a WoW folder", client=False).add_argument("path")
    add("desktop", cmd_desktop, "app launcher entry", client=False).add_argument("action", choices=["install", "remove"])
    add("timer", cmd_timer, "background updates", client=False).add_argument("action", choices=["on", "off"])
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    cfg = Config()
    if not argv:
        return cmd_gui(argparse.Namespace(uri=""), cfg) or 0
    if "://" in argv[0]:
        return cmd_gui(argparse.Namespace(uri=argv[0]), cfg) or 0
    args = build_parser().parse_args(argv)
    if not getattr(args, "fn", None):
        return cmd_gui(argparse.Namespace(uri=""), cfg) or 0
    return args.fn(args, cfg) or 0
