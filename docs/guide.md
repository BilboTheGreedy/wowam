# Guide

## Installs

The app looks for World of Warcraft in the usual places: the default folders on Windows and macOS, and Lutris, Steam, Bottles and plain Wine prefixes on Linux. Every game version in a folder (Retail, Classic, Classic Era, Forever, PTR and so on) is listed on its own in the sidebar.

If yours is somewhere else, click "Add WoW folder" and pick the World of Warcraft folder.

## Installed tab

Lists every addon in the selected install. Addons you installed by hand are matched to their source when the app can find it, so they get updates too.

- **Update** on a row, or **Update all** at the top
- **OUT OF DATE** means the addon was made for an older game version. It may still work.
- **Needs X** means an addon it depends on is missing. Click it to find it.
- **Changed by you** means files were edited after install. These are skipped by Update all so your changes are not lost.

The menu on each row:

| Item | What it does |
|---|---|
| What's new | the changelog of the latest version |
| Go back to ... | puts the previous version back and pins it |
| Reinstall | downloads the current version again |
| Pin this version | stops updates for this addon |
| Include beta releases | also offers alpha and beta versions |
| Change source | point the addon at another link |
| Forget source | keep the files but stop tracking them |
| Remove | deletes the addon folders |

Shortcuts: F5 refresh, Ctrl+U update all, Ctrl+F search, Ctrl+, settings.

## Browse tab

Search by name or paste a link. These work:

- `https://github.com/owner/repo` or `gh:owner/repo`, also projects that have no releases
- `https://www.wowinterface.com/downloads/info12345` or `wowi:12345`
- `tukui:elvui`, `tukui:tukui`
- `https://addons.wago.io/addons/name` or `wago:name` (needs a Wago key)
- `https://www.curseforge.com/wow/addons/name` or `cf:name` (needs a CurseForge key)

"Only addons listed for ..." hides results the author has not marked for your game version.

When the search box is empty, Browse shows the shared setups. See the [readme](../README.md#shared-addon-setups).

## Sources and keys

| Source | Needs |
|---|---|
| GitHub | nothing. A token in Settings raises the hourly limit. If the GitHub CLI is signed in, that is used. |
| WoWInterface | nothing |
| Tukui | nothing |
| Wago Addons | a key, which Wago gives to its supporters |
| CurseForge | a key from console.curseforge.com. It is free but you have to apply. Some authors only allow the CurseForge app. |

Keys are kept in the config file on your computer and only sent to the service they belong to.

## Backups

A backup is a zip of the WTF folder, where the game keeps addon settings, keybinds and macros. By default one is made before updates, and the last 7 are kept. Settings has "Back up now", the list of backups and restore.

"Leftover settings" finds saved settings of addons you no longer have and can delete them. It makes a backup first.

## WeakAuras

Auras you imported from wago.io are checked for new versions. The app writes a small helper addon called WowamCompanion, and WeakAuras then offers the updates in game the next time you log in or reload. Turn it off in Settings if you do not want it.

## Automatic things

All in Settings, all off by default except the update notice and WeakAuras:

- **Start when I log in**
- **Keep running in the tray**: closing the window leaves a tray icon that checks every two hours
- **Update addons when the app opens**
- **Update addons in the background**: every six hours, with a notification
- **Tell me about new versions of this app**: shows a banner with "Update and restart"

## Play button

Starts the game for the selected install. On Linux it goes through Lutris or Steam when the install belongs to one of them, otherwise through Wine.

## Moving addons around

- Settings, Addon list, "Copy my addon list" gives you one line of text. Paste it into the same card on another install or computer.
- "Install the addons from ..." copies them straight from another install on the same computer.
- Or share it as a link, see the readme.

## Command line

The same things work from a terminal:

```
wowam status            show addons and updates
wowam update            update addons
wowam install <links>   install addons
wowam remove <names>    remove addons
wowam pin <names>       stop updating an addon
wowam backup            back up settings
wowam export            print the addon list
wowam import <list>     install a list or a link to one
wowam auto              update everything quietly
wowam self-update       update wowam itself
```

Add `-c retail` to choose an install, or `-a` for all of them. `wowam --help` lists everything.

## Where files are kept

| | Linux | Windows | macOS |
|---|---|---|---|
| settings | `~/.config/wowam` | `%APPDATA%\wowam` | `~/Library/Application Support/wowam` |
| backups, history | `~/.local/share/wowam` | `%LOCALAPPDATA%\wowam` | `~/Library/Application Support/wowam` |

Which addons are tracked is saved per install in `WTF/wowam.json`.
