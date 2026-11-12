# Guide

## Installs

The app looks for World of Warcraft in the usual places: the default folders on Windows and macOS, and Lutris, Steam, Bottles and plain Wine prefixes on Linux. Every game version in a folder (Retail, Classic, Classic Era, Forever, PTR and so on) is listed on its own in the sidebar.

If yours is somewhere else, click "Add WoW folder" and pick the World of Warcraft folder.

## Installed tab

Lists every addon in the selected install. Addons you installed by hand are matched to their source when the app can find it, so they get updates too.

- **Update** on a row, or **Update all** at the top
- **OUT OF DATE** means the addon was made for an older game version. It may still work.
- **Needs X** means an addon it depends on is missing. "Find it" installs it when the app knows where it is, otherwise it searches for it.
- **NO UPDATE SINCE 2023** (or another year) means the author has not released anything for two years or more.
- **Changed by you** means files were edited after install. These are skipped by Update all so your changes are not lost.

The menu on each row:

| Item | What it does |
|---|---|
| What's new | the changelog of the latest version |
| Go back to ... | puts the previous version back and pins it |
| Reinstall | downloads the current version again |
| Turn off / Turn on | moves the addon out of the AddOns folder into `Interface/AddOns.off` so the game does not load it, and back again |
| Put back settings from last backup | restores only this addon's saved settings from the newest backup |
| Add a note | a line of your own that shows on the row |
| Pin this version | stops updates for this addon |
| Include beta releases | also offers alpha and beta versions |
| Change source | point the addon at another link |
| Forget source | keep the files but stop tracking them |
| Remove | deletes the addon folders |

**Undo last update**: after "Update all" the button turns into "Undo last update". It puts the previous version of every addon from that round back and pins them.

**Problems from the game**: if the game logged that an addon did not load, or BugGrabber recorded errors for it since you last installed or updated it, the row says so, for example "Did not load in the game: needs Ace3" or "12 errors in the game".

**Profiles**: the Profiles button saves which addons are turned on under a name, for example Raid or Levelling. Switching to a profile turns the other addons off without removing them. "Turn off out of date addons" is for patch day: it saves a profile called Before safe mode first, so one click brings everything back.

"Needs attention" next to the filter shows only addons with an update, an error, your own changes or an out of date mark. Handy after a game patch.

Shortcuts: F5 refresh, Ctrl+U update all, Ctrl+F search, Ctrl+, settings.

## Browse tab

Search by name or paste a link. These work:

- `https://github.com/owner/repo` or `gh:owner/repo`, also projects that have no releases
- `https://www.wowinterface.com/downloads/info12345` or `wowi:12345`
- `tukui:elvui`, `tukui:tukui`
- `https://addons.wago.io/addons/name` or `wago:name` (needs a Wago key)
- `https://www.curseforge.com/wow/addons/name` or `cf:name` (needs a CurseForge key)

**From a zip file**: drop a zip onto the window, or use "From a zip file" in Browse. The app installs it and then tries to find where it comes from, so it can get updates. If it cannot, the addon stays as it is and you can set a source from its menu.

"Only addons listed for ..." hides results the author has not marked for your game version.

When the search box is empty, Browse shows the shared setups. See the [readme](../README.md#shared-addon-setups).

## Following a setup

When you open a shared setup you can turn on "Follow this setup". From then on the app looks at the setup when it checks for updates. If the author added or dropped addons you get a notice on the Installed tab with "Review". Applying installs the new ones. Dropped ones are only removed if you tick that.

Settings, Addon list shows what you follow and has "Stop following".

## Interface packs

A pack is a zip with a `wowam-ui.json` (name and addon list) and a `WTF` folder holding the addon settings of one character, with the names replaced by placeholders.

Importing:

1. Close the game.
2. Drop the zip onto the window, use "From a zip file" in Browse, or paste a link that ends in `.zip`.
3. Pick the character that should get the settings. If the pack holds more than one character, pick which one to copy.
4. The app makes a backup, copies the account settings to your account and the character settings to your character, changes profile names such as `Thrall - Tarren Mill` to your own, and installs the addons.

Under "Settings to take" you can untick addons whose settings you want to keep as they are. "replaces yours" marks the ones you already have settings for.

The character has to exist in the game folder, so log in with it once before importing. Only addon settings are touched, not keybinds or macros. To undo, restore the backup in Settings.

Hand-made packs with `Interface/AddOns` and `WTF/Account/...` inside work the same way. The addons in them are copied in as they are.

**Between your own characters**: Settings, Addon list, "Copy my interface to another character". The second character gets the first one's addon settings and is pointed at the same profiles, so a change on one shows on the other.

Making one: Settings, Addon list, "Save my interface as a pack". Pick the character and untick addons you want to leave out. Your account name, character, realm and alts are replaced with placeholders. Names of friends and guild members cannot be found automatically, so leave out addons that keep that kind of data (chat, friend list, damage history) and have a look in the zip before you post it.

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

"Disk space" in Settings measures how much room the addons, saved settings, backups and kept previous versions take.

"Leftover settings" finds saved settings of addons you no longer have and can delete them. It makes a backup first.

## WeakAuras

Auras you imported from wago.io are checked for new versions. The app writes a small helper addon called WowamCompanion, and WeakAuras then offers the updates in game the next time you log in or reload. Turn it off in Settings if you do not want it.

## Automatic things

While the window is open the app checks for updates when it starts, when you switch installs, when you press refresh, and every two hours.

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
