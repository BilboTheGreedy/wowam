# World of Warcraft addon manager (wowam)

Addon manager with a GUI for WoW on Linux, Windows and macOS. Works with every WoW version, including Classic and Forever.

Windows: get `wowam-setup.exe` from [Releases](https://github.com/BilboTheGreedy/wowam/releases/latest). Linux: `curl -fsSL https://raw.githubusercontent.com/BilboTheGreedy/wowam/main/install.sh | sh`. From source: `./run` (needs python and pyside6).

## Shared addon setups

Install someone's whole addon setup in one click, or publish your own for others.

![shared setups](docs/shared-setups.png)

**Install a setup**

- Open Browse. Shared setups are listed there. Click one to see what is in it, then install.
- Or paste a link to a list into the search box. A gist or any `.txt` file in a GitHub repo works.

**Share yours**

- Click "Share mine" in Browse. It opens GitHub with your addon list filled in, you give it a name and send it. It shows up in the app for everyone once it is merged into [wowam-lists](https://github.com/BilboTheGreedy/wowam-lists).
- Or keep it to yourself and your friends: put the list in a gist and send them the link.

A list is just a text file:

```
# name: Raid basics
# by: yourname
# for: Retail
# about: boss mods and a damage meter
gh:BigWigsMods/BigWigs
https://github.com/WeakAuras/WeakAuras2
wowi:12345
```

The same list works on any WoW version, the app picks the right files for the install you put it on.

## Other things it does

- finds your WoW installs, also under Lutris, Steam and Wine
- installs and updates from GitHub, WoWInterface and Tukui, plus Wago and CurseForge with your own key
- any GitHub addon link works, also projects without releases
- changelogs, pin a version, go back to the previous one
- backs up your settings folder before updates
- updates WeakAuras imported from wago.io
- tray icon, start at login, updates itself
