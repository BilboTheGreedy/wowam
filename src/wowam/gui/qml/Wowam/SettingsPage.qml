import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Wowam

Item {
    id: root
    signal addFolderRequested()

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
                title: "Automatic"
                Line {
                    label: "Start wowam when I log in"
                    Toggle { checked: backend.autostart; Accessible.name: "Start wowam when I log in"; onToggled: backend.setAutostart(checked) }
                }
                Line {
                    label: "Update addons when wowam opens"
                    detail: "Installs every available update for all your installs as soon as the window opens. Pinned addons and ones you changed are left alone."
                    Toggle { checked: backend.updateOnStart; Accessible.name: "Update addons when wowam opens"; onToggled: backend.setUpdateOnStart(checked) }
                }
                Line {
                    label: "Update addons in the background"
                    detail: "Checks every six hours while you are logged in and shows a notification when something was updated."
                    Toggle { checked: backend.timer; Accessible.name: "Update addons in the background"; onToggled: backend.setTimer(checked) }
                }
                Line {
                    label: "Show wowam in the app launcher"
                    detail: "Also lets install links on the Wago Addons website open here."
                    Toggle { checked: backend.launcher; Accessible.name: "Show wowam in the app launcher"; onToggled: backend.setLauncher(checked) }
                }
                Line {
                    label: "Tell me about new wowam versions"
                    detail: "Checks the wowam page on GitHub when the window opens."
                    Toggle { checked: backend.checkUpdates; Accessible.name: "Tell me about new wowam versions"; onToggled: backend.setCheckUpdates(checked) }
                }
            }

            Card {
                title: "Settings backup" + (backend.hasClient ? "  ·  " + backend.clientLabel : "")
                hint: "A backup is a copy of the WTF folder, where the game keeps your addon settings, keybinds and macros."
                Line {
                    label: "Back up before updating"
                    Toggle { checked: backend.backupOnUpdate; Accessible.name: "Back up before updating"; onToggled: backend.setBackupOnUpdate(checked) }
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
                    detail: "Optional. Without one, GitHub allows about 60 checks an hour, which is enough for most addon lists. A token with no extra permissions raises that limit."
                }
                Secret {
                    label: "Wago Addons API key"
                    value: backend.wagoKey
                    settingKey: "wago_key"
                    detail: "Optional. Wago gives keys to its supporters. With a key, addons that are only on Wago can be installed and updated."
                }
            }

            Card {
                title: "Addon list" + (backend.hasClient ? "  ·  " + backend.clientLabel : "")
                hint: "Copy the list to move your addons to another install or computer, then paste it there."
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Field {
                        id: listField
                        Layout.fillWidth: true
                        placeholderText: "Paste an addon list or several links"
                        Accessible.name: "Addon list to install"
                    }
                    Btn {
                        text: "Install all"
                        kind: "primary"
                        enabled: listField.text.trim().length > 0 && backend.hasClient
                        onClicked: if (backend.installList(listField.text) > 0) listField.text = ""
                    }
                }
                Btn { text: "Copy my addon list"; iconName: "copy"; enabled: backend.hasClient; onClicked: backend.copyList() }
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
                text: "wowam " + backend.version
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
