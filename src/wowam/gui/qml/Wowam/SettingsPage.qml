import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Wowam

Item {
    id: root
    signal addFolderRequested()
    signal tourRequested()
    property alias tourAuto: autoCard
    property alias tourList: listCard

    function reveal(item) {
        flick.contentY = Math.max(0, Math.min(item.y + col.y - 24, flick.contentHeight - flick.height))
    }

    component Line: RowLayout {
        property string label: ""
        property string detail: ""
        default property alias control: holder.data
        Layout.fillWidth: true
        spacing: 16
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text { text: parent.parent.label; color: Theme.text; font.pixelSize: Theme.body; font.weight: Font.Medium; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Text {
                visible: text !== ""
                text: parent.parent.detail
                color: Theme.sub
                font.pixelSize: Theme.small
                wrapMode: Text.WordWrap
                lineHeight: 1.2
                Layout.fillWidth: true
            }
        }
        RowLayout { id: holder; spacing: 8 }
    }

    component Secret: ColumnLayout {
        id: secret
        property string label: ""
        property string detail: ""
        property string value: ""
        property string settingKey: ""
        Layout.fillWidth: true
        spacing: 6
        Text { text: secret.label; color: Theme.text; font.pixelSize: Theme.body; font.weight: Font.Medium }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Field {
                id: input
                Layout.fillWidth: true
                text: secret.value
                echoMode: reveal.checked ? TextInput.Normal : TextInput.Password
                placeholderText: "Not set"
                Accessible.name: secret.label
                onEditingFinished: if (text !== secret.value) backend.setText(secret.settingKey, text)
            }
            Btn { id: reveal; checkable: true; kind: "ghost"; text: checked ? "Hide" : "Show" }
            Btn { text: "Save"; enabled: input.text !== secret.value; onClicked: backend.setText(secret.settingKey, input.text) }
        }
        Text { text: secret.detail; color: Theme.sub; font.pixelSize: Theme.small; wrapMode: Text.WordWrap; lineHeight: 1.2; Layout.fillWidth: true }
    }

    Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: col.implicitHeight + 56
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: col
            x: 28
            y: 24
            width: Math.min(flick.width - 56, 760)
            spacing: 14

            Text {
                text: "Settings"
                color: Theme.text
                font.pixelSize: Theme.title
                font.weight: Font.Bold
                Layout.bottomMargin: 6
            }

            Card {
                id: autoCard
                title: "Automatic"
                Line {
                    label: "Start when I log in"
                    Toggle { value: backend.autostart; Accessible.name: "Start when I log in"; onRequested: (on) => backend.setAutostart(on) }
                }
                Line {
                    visible: backend.trayAvailable
                    label: "Keep running in the tray"
                    detail: "Closing the window leaves an icon in the system tray that checks for updates every two hours. With Start when I log in, the app starts there without opening a window."
                    Toggle { value: backend.trayOn; Accessible.name: "Keep running in the tray"; onRequested: (on) => backend.setTray(on) }
                }
                Line {
                    label: "Update addons when the app opens"
                    detail: "Installs every available update for all your installs as soon as the window opens. Pinned addons and ones you changed are left alone."
                    Toggle { value: backend.updateOnStart; Accessible.name: "Update addons when the app opens"; onRequested: (on) => backend.setUpdateOnStart(on) }
                }
                Line {
                    label: "Update addons in the background"
                    detail: "Checks every six hours while you are logged in and shows a notification when something was updated."
                    Toggle { value: backend.timer; Accessible.name: "Update addons in the background"; onRequested: (on) => backend.setTimer(on) }
                }
                Line {
                    label: "Check WeakAuras for updates"
                    detail: "Looks up the auras you imported from wago.io and hands new versions to WeakAuras, which offers them the next time you log in or reload."
                    Toggle { value: backend.auraUpdates; Accessible.name: "Check WeakAuras for updates"; onRequested: (on) => backend.setAuraUpdates(on) }
                }
                Line {
                    label: "Show in the app launcher"
                    detail: "Also lets install links on the Wago Addons website open here."
                    Toggle { value: backend.launcher; Accessible.name: "Show in the app launcher"; onRequested: (on) => backend.setLauncher(on) }
                }
                Line {
                    label: "Tell me about new versions of this app"
                    detail: "Checks the project page on GitHub when the window opens."
                    Toggle { value: backend.checkUpdates; Accessible.name: "Tell me about new versions of this app"; onRequested: (on) => backend.setCheckUpdates(on) }
                }
            }

            Card {
                title: "Appearance"
                Line {
                    label: "Theme"
                    Repeater {
                        model: [["", "System"], ["light", "Light"], ["dark", "Dark"]]
                        Btn {
                            required property var modelData
                            text: modelData[1]
                            kind: backend.themeMode === modelData[0] ? "accent" : "ghost"
                            onClicked: backend.setTheme(modelData[0])
                        }
                    }
                }
                Line {
                    label: "Tour"
                    Btn { text: "Show the tour again"; onClicked: root.tourRequested() }
                }
            }

            Card {
                title: "Recent changes"
                hint: "What was installed, updated or rolled back lately, including background updates."
                Repeater {
                    model: backend.history
                    RowLayout {
                        id: historyRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 10
                        Text { text: historyRow.modelData.name; color: Theme.text; font.pixelSize: Theme.body; font.weight: Font.Medium; elide: Text.ElideRight; Layout.preferredWidth: 180 }
                        Text { text: historyRow.modelData.change; color: Theme.sub; font.pixelSize: Theme.small; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        Text { text: historyRow.modelData.where + "  ·  " + historyRow.modelData.when; color: Theme.faint; font.pixelSize: Theme.small }
                    }
                }
                Text {
                    visible: backend.history.length === 0
                    text: "Nothing yet."
                    color: Theme.sub
                    font.pixelSize: Theme.small
                }
            }

            Card {
                title: "Settings backup" + (backend.hasClient ? "  ·  " + backend.clientLabel : "")
                hint: "A backup is a copy of the WTF folder, where the game keeps your addon settings, keybinds and macros."
                Line {
                    label: "Back up before updating"
                    Toggle { value: backend.backupOnUpdate; Accessible.name: "Back up before updating"; onRequested: (on) => backend.setBackupOnUpdate(on) }
                }
                Line {
                    label: "Backups to keep"
                    Btn { text: "−"; implicitWidth: 34; enabled: backend.backupKeep > 1; Accessible.name: "Keep fewer backups"; onClicked: backend.setBackupKeep(backend.backupKeep - 1) }
                    Text { text: backend.backupKeep; color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter; Layout.preferredWidth: 26 }
                    Btn { text: "+"; implicitWidth: 34; enabled: backend.backupKeep < 50; Accessible.name: "Keep more backups"; onClicked: backend.setBackupKeep(backend.backupKeep + 1) }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                Repeater {
                    model: backend.backups
                    RowLayout {
                        id: backupRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 10
                        Icon { shape: "archive"; size: 16 }
                        Text { text: backupRow.modelData.when; color: Theme.text; font.pixelSize: Theme.body }
                        Text { text: backupRow.modelData.size; color: Theme.sub; font.pixelSize: Theme.small; Layout.fillWidth: true }
                        Btn { text: "Restore"; kind: "ghost"; onClicked: restoreDialog.show(backupRow.modelData) }
                    }
                }
                Text {
                    visible: backend.backups.length === 0
                    text: "No backups yet."
                    color: Theme.sub
                    font.pixelSize: Theme.small
                }
                Btn { text: "Back up now"; iconName: "archive"; enabled: backend.hasClient; onClicked: backend.backupNow() }
            }

            Card {
                title: "Addon sources"
                Secret {
                    label: "GitHub token"
                    value: backend.githubToken
                    settingKey: "github_token"
                    detail: "Optional. Without one, GitHub allows about 60 checks an hour, which is enough for most addon lists. A token with no extra permissions raises that limit, and sharing a setup as a link also needs the gist permission. If you are signed in with the GitHub CLI, the app uses that and you can leave this empty."
                }
                Secret {
                    label: "CurseForge API key"
                    value: backend.curseKey
                    settingKey: "curseforge_key"
                    detail: backend.curseBuiltin ? "Not needed. This build already has CurseForge access; a key here is used instead of the built-in one." : "Optional. Keys cost nothing but you have to apply for one at console.curseforge.com. With a key, CurseForge addons show up in Browse and can be installed and updated, except the ones whose authors only allow the CurseForge app."
                }
                Secret {
                    label: "Wago Addons API key"
                    value: backend.wagoKey
                    settingKey: "wago_key"
                    detail: "Optional. Wago gives keys to its supporters. With a key, addons that are only on Wago can be installed and updated."
                }
            }

            Card {
                id: listCard
                title: "Addon list" + (backend.hasClient ? "  ·  " + backend.clientLabel : "")
                hint: "The list works on every WoW version. Copy it to move your addons to another install or computer, or paste a list or a link to one that someone shared."
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Field {
                        id: listField
                        Layout.fillWidth: true
                        placeholderText: "Paste an addon list, several links, or a link to a shared list"
                        Accessible.name: "Addon list to install"
                    }
                    Btn {
                        text: "Install all"
                        kind: "primary"
                        enabled: listField.text.trim().length > 0 && backend.hasClient
                        onClicked: if (backend.installList(listField.text) > 0) listField.text = ""
                    }
                }
                RowLayout {
                    spacing: 8
                    Btn { text: "Copy my addon list"; iconName: "copy"; enabled: backend.hasClient; onClicked: backend.copyList() }
                    Btn { text: "Share it as a link"; iconName: "link"; enabled: backend.hasClient; onClicked: backend.openShare() }
                    Btn { text: "Save my interface as a pack"; iconName: "archive"; enabled: backend.hasClient; onClicked: backend.openExport() }
                }
                RowLayout {
                    spacing: 8
                    Btn { text: "Copy my interface to another character"; iconName: "copy"; enabled: backend.hasClient; onClicked: backend.openCopy() }
                }
                Repeater {
                    model: backend.follows
                    RowLayout {
                        id: followRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            Layout.fillWidth: true
                            text: "Following " + followRow.modelData.name + "  ·  " + followRow.modelData.count + " addons"
                            color: Theme.text
                            font.pixelSize: Theme.body
                            elide: Text.ElideRight
                        }
                        Btn { text: "Stop following"; kind: "ghost"; onClicked: backend.unfollow(followRow.modelData.url) }
                    }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: backend.otherClients.length > 0
                    Repeater {
                        model: backend.otherClients
                        Btn {
                            required property var modelData
                            text: "Install the addons from " + modelData.label
                            iconName: "download"
                            onClicked: backend.copyFrom(modelData.key)
                        }
                    }
                }
            }

            Card {
                title: "Disk space" + (backend.hasClient ? "  ·  " + backend.clientLabel : "")
                Repeater {
                    model: backend.usage
                    RowLayout {
                        id: use
                        required property var modelData
                        Layout.fillWidth: true
                        Text { Layout.fillWidth: true; text: use.modelData.label; color: Theme.text; font.pixelSize: Theme.body; elide: Text.ElideRight }
                        Text { text: use.modelData.size; color: Theme.sub; font.pixelSize: Theme.body }
                    }
                }
                Btn { text: backend.usage.length > 0 ? "Measure again" : "Measure"; enabled: backend.hasClient; onClicked: backend.measure() }
            }

            Card {
                title: "Leftover settings" + (backend.hasClient ? "  ·  " + backend.clientLabel : "")
                hint: "Removed addons leave their saved settings behind. Finding them changes nothing; deleting makes a backup first."
                Text {
                    visible: backend.orphansScanned
                    text: backend.orphanSummary
                    color: Theme.text
                    font.pixelSize: Theme.body
                    wrapMode: Text.WordWrap
                    lineHeight: 1.25
                    Layout.fillWidth: true
                }
                RowLayout {
                    spacing: 8
                    Btn { text: backend.orphansScanned ? "Look again" : "Find leftovers"; iconName: "search"; enabled: backend.hasClient; onClicked: backend.scanOrphans() }
                    Btn { text: backend.orphanCount === 1 ? "Delete 1 file" : "Delete " + backend.orphanCount + " files"; kind: "danger"; visible: backend.orphanCount > 0; onClicked: orphanDialog.open() }
                }
            }

            Card {
                title: "Extra WoW folders"
                hint: "Installs in the usual places are found automatically. Add a folder here when yours is somewhere else."
                Repeater {
                    model: backend.extraPaths
                    RowLayout {
                        id: pathRow
                        required property string modelData
                        Layout.fillWidth: true
                        spacing: 10
                        Icon { shape: "folder"; size: 16 }
                        Text { text: pathRow.modelData; color: Theme.text; font.pixelSize: Theme.body; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        Btn { text: "Remove"; kind: "ghost"; onClicked: backend.removeFolder(pathRow.modelData) }
                    }
                }
                Btn { text: "Add WoW folder"; iconName: "plus"; onClicked: root.addFolderRequested() }
            }

            Text {
                text: backend.fullName + " " + backend.version
                color: Theme.faint
                font.pixelSize: Theme.small
                Layout.topMargin: 4
            }
        }
    }

    Modal {
        id: restoreDialog
        property string name: ""
        function show(entry) {
            name = entry.name
            title = "Restore settings from " + entry.when + "?"
            open()
        }
        message: "This replaces the current settings of " + backend.clientLabel + " with the backup. The current settings are backed up first. Close the game before restoring."
        confirmText: "Restore"
        onConfirmed: { backend.restoreBackup(name); close() }
    }

    Modal {
        id: orphanDialog
        title: backend.orphanCount === 1 ? "Delete 1 leftover file?" : "Delete " + backend.orphanCount + " leftover files?"
        message: backend.orphanSummary + "\n\nA backup is made first, so this can be undone from Settings backup."
        confirmText: "Delete"
        danger: true
        onConfirmed: { backend.cleanOrphans(); close() }
    }
}
