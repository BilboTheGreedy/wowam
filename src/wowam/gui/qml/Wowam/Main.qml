import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import Wowam

ApplicationWindow {
    id: window
    width: 1120
    height: 740
    minimumWidth: 780
    minimumHeight: 520
    visible: false
    title: backend.fullName
    color: Theme.bg

    property bool settingsOpen: false

    onVisibleChanged: if (visible && backend.welcomeNeeded) tour.start()

    onClosing: (close) => {
        if (backend.trayOn) {
            close.accepted = false
            window.hide()
        } else {
            Qt.quit()
        }
    }

    Binding { target: Theme; property: "mode"; value: backend.themeMode }

    Shortcut { sequences: ["F5", "Ctrl+R"]; onActivated: backend.refresh() }
    Shortcut { sequence: "Ctrl+U"; onActivated: backend.updateAll() }
    Shortcut { sequence: "Ctrl+F"; onActivated: { window.settingsOpen = false; addonsPage.focusSearch() } }
    Shortcut { sequence: "Ctrl+,"; onActivated: window.settingsOpen = !window.settingsOpen }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Sidebar {
            Layout.preferredWidth: 236
            Layout.fillHeight: true
            settingsOpen: window.settingsOpen
            onClientPicked: (index) => { window.settingsOpen = false; backend.selectClient(index); addonsPage.clientChanged() }
            onSettingsClicked: window.settingsOpen = !window.settingsOpen
            onAddClicked: folderDialog.open()
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Rectangle {
                visible: backend.updateVersion !== ""
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                color: Theme.accentSoft
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 28
                    anchors.rightMargin: 16
                    spacing: 12
                    Icon { shape: "download"; size: 17; color: Theme.accentText }
                    Text {
                        Layout.fillWidth: true
                        text: backend.updating
                            ? "Downloading version " + backend.updateVersion + "  ·  " + Math.round(backend.updateProgress * 100) + "%"
                            : "Version " + backend.updateVersion + " of " + backend.appName + " is available. You have " + backend.version + "."
                        color: Theme.text
                        font.pixelSize: Theme.body
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                    }
                    Btn {
                        visible: !backend.updating
                        kind: "primary"
                        implicitHeight: 30
                        text: backend.updateInstallable ? "Update and restart" : "Open download page"
                        onClicked: backend.installUpdate()
                    }
                    IconBtn {
                        visible: !backend.updating
                        iconName: "close"
                        tip: "Not now"
                        implicitWidth: 30
                        implicitHeight: 30
                        Accessible.name: "Dismiss update notice"
                        onClicked: backend.dismissUpdate()
                    }
                }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: window.settingsOpen ? 1 : 0
                AddonsPage { id: addonsPage; onAddFolderRequested: folderDialog.open(); onZipRequested: zipDialog.open() }
                SettingsPage { onAddFolderRequested: folderDialog.open(); onTourRequested: tour.start() }
            }
        }
    }

    FileDialog {
        id: zipDialog
        title: "Choose an addon zip file"
        nameFilters: ["Zip files (*.zip)"]
        onAccepted: backend.installFile(selectedFile.toString())
    }

    DropArea {
        anchors.fill: parent
        enabled: backend.hasClient
        onEntered: (drag) => { drag.accepted = drag.hasUrls }
        onDropped: (drop) => {
            for (var i = 0; i < drop.urls.length; i++) {
                var u = drop.urls[i].toString()
                if (u.toLowerCase().endsWith(".zip")) backend.installFile(u)
            }
        }
    }

    FolderDialog {
        id: folderDialog
        title: "Choose your World of Warcraft folder"
        onAccepted: backend.addFolder(selectedFolder.toString())
    }

    Connections {
        target: backend
        function onToast(message, isError) { toast.show(message, isError) }
        function onListReady(item) { listDialog.show(item) }
        function onShareRequested(data) { shareDialog.show(data) }
        function onPackReady(data) { packDialog.show(data) }
        function onExportRequested(data) { exportDialog.show(data) }
        function onCopyRequested(data) { copyDialog.show(data) }
        function onPublished(url) { shareDialog.busy = false; shareDialog.link = url }
        function onShowBrowse(text) {
            window.settingsOpen = false
            addonsPage.browseFor(text)
            window.raise()
            window.requestActivate()
        }
    }

    Modal {
        id: tour
        property int step: 0
        readonly property var steps: [
            {
                title: "Welcome",
                text: "This app finds your World of Warcraft installs and keeps their addons up to date. The installs are listed on the left. This tour takes about a minute."
            },
            {
                title: "Your addons",
                text: "The Installed tab lists every addon in the selected install. When a new version is out the addon gets an Update button, and Update all does them in one go. The menu on each row has the changelog, pinning and going back a version."
            },
            {
                title: "Find more addons",
                text: "In Browse, search by name or paste a link from GitHub, WoWInterface, CurseForge or Wago. Any GitHub addon link works, and the addon is kept up to date from then on. You can also drop a downloaded zip file onto the window."
            },
            {
                title: "Shared setups",
                text: "Browse also lists whole addon setups that other players have published. Open one to see what is in it, then install the lot. Share mine turns your own addons into a link you can send to friends, who paste it into Browse."
            },
            {
                title: "Settings and backups",
                text: "Settings has backups of your game settings, automatic updates, starting at login and the tray icon. You can replay this tour from there."
            }
        ]
        function start() {
            step = 0
            place()
            open()
        }
        function place() {
            window.settingsOpen = step === 4
            if (step < 4) addonsPage.showTab(step >= 2 ? 1 : 0)
        }
        title: steps[step].title
        message: steps[step].text
        cancelText: "Skip"
        showCancel: step < steps.length - 1
        confirmText: step < steps.length - 1 ? "Next" : "Done"
        closePolicy: Popup.CloseOnEscape
        onConfirmed: {
            if (step < steps.length - 1) {
                step += 1
                place()
            } else {
                close()
            }
        }
        onClosed: {
            backend.setWelcomed()
            window.settingsOpen = false
            addonsPage.showTab(0)
        }
        RowLayout {
            spacing: 6
            Repeater {
                model: tour.steps.length
                Rectangle {
                    required property int index
                    implicitWidth: index === tour.step ? 18 : 6
                    implicitHeight: 6
                    radius: 3
                    color: index === tour.step ? Theme.accent : Theme.tint(Theme.sub, 0.35)
                }
            }
        }
    }

    component Picker: ListView {
        id: picker
        property string picked: ""
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(contentHeight, 150)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        delegate: RowLayout {
            id: opt
            required property var modelData
            readonly property bool on: picker.picked === modelData.key
            width: ListView.view.width - 12
            height: 30
            spacing: 10
            Accessible.role: Accessible.RadioButton
            Accessible.name: modelData.label
            Accessible.checked: on
            TapHandler { onTapped: picker.picked = opt.modelData.key }
            Rectangle {
                implicitWidth: 18
                implicitHeight: 18
                radius: 9
                color: "transparent"
                border.color: opt.on ? Theme.accent : Theme.sub
                border.width: opt.on ? 5 : 1.5
            }
            Text {
                Layout.fillWidth: true
                text: opt.modelData.label
                color: Theme.text
                font.pixelSize: Theme.body
                elide: Text.ElideRight
            }
        }
    }

    component Caption: Text {
        Layout.fillWidth: true
        Layout.topMargin: 4
        color: Theme.sub
        font.pixelSize: Theme.small
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
    }

    Modal {
        id: packDialog
        property var pack: ({ path: "", sources: [], targets: [], addons: 0, bundled: 0, files: 0, settings: [], other: false })
        property var off: ({})
        property var mine: []
        readonly property int picked: pack.settings.filter(n => !off[n]).length
        function toggle(name) {
            var next = Object.assign({}, off)
            next[name] = !next[name]
            off = next
        }
        function show(data) {
            pack = data
            off = ({})
            mine = []
            title = "Import " + data.name
            var bits = []
            if (data.by) bits.push("by " + data.by)
            if (data.game) bits.push(data.game)
            bits.push(data.files + " settings files")
            if (data.addons) bits.push(data.addons + " addons to install")
            if (data.bundled) bits.push(data.bundled + " addons included")
            message = bits.join("  ·  ")
            fromPick.picked = data.sources.length > 0 ? data.sources[0].key : ""
            toPick.picked = data.targets.length === 1 ? data.targets[0].key : ""
            open()
        }
        width: Math.min(520, parent ? parent.width - 48 : 520)
        confirmText: "Import to " + backend.clientLabel
        confirmEnabled: toPick.picked !== "" && (picked > 0 || pack.settings.length === 0)
        onConfirmed: {
            backend.importPack(pack.path, fromPick.picked, toPick.picked, pack.settings.filter(n => off[n]).join("|"))
            close()
        }
        Caption { visible: packDialog.pack.sources.length > 1; text: "Copy the settings of" }
        Picker { id: fromPick; visible: packDialog.pack.sources.length > 1; model: packDialog.pack.sources }
        Caption { visible: packDialog.pack.targets.length > 0; text: "Give them to your character" }
        Picker {
            id: toPick
            model: packDialog.pack.targets
            onPickedChanged: packDialog.mine = picked ? backend.packOverwrites(picked) : []
        }
        Caption { visible: packDialog.pack.settings.length > 0; text: "Settings to take" }
        ListView {
            visible: packDialog.pack.settings.length > 0
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, 150)
            clip: true
            model: packDialog.pack.settings
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: RowLayout {
                id: take
                required property string modelData
                readonly property bool on: !packDialog.off[modelData]
                width: ListView.view.width - 12
                height: 30
                spacing: 10
                Accessible.role: Accessible.CheckBox
                Accessible.name: modelData
                Accessible.checked: on
                TapHandler { onTapped: packDialog.toggle(take.modelData) }
                Rectangle {
                    implicitWidth: 18
                    implicitHeight: 18
                    radius: 5
                    color: take.on ? Theme.accent : "transparent"
                    border.color: take.on ? Theme.accent : Theme.sub
                    Icon { anchors.centerIn: parent; visible: take.on; shape: "check"; size: 12; color: Theme.onAccent }
                }
                Text {
                    Layout.fillWidth: true
                    text: take.modelData
                    color: take.on ? Theme.text : Theme.sub
                    font.pixelSize: Theme.body
                    elide: Text.ElideRight
                }
                Text {
                    visible: take.on && packDialog.mine.indexOf(take.modelData.toLowerCase()) >= 0
                    text: "replaces yours"
                    color: Theme.warn
                    font.pixelSize: Theme.small
                }
            }
        }
        Text {
            visible: packDialog.pack.other
            Layout.fillWidth: true
            text: "This pack was made on " + packDialog.pack.game + ". Some of its addons or settings may not fit " + backend.clientLabel + "."
            color: Theme.warn
            font.pixelSize: Theme.small
            wrapMode: Text.WordWrap
        }
        Text {
            Layout.fillWidth: true
            text: packDialog.pack.targets.length === 0
                ? "No characters found in " + backend.clientLabel + ". Log in to the game with your character once, then import again."
                : "Your current settings are backed up first, so you can go back in Settings. Close the game before importing."
            color: Theme.sub
            font.pixelSize: Theme.small
            wrapMode: Text.WordWrap
        }
    }

    Modal {
        id: copyDialog
        property var info: ({ chars: [], game: "" })
        function show(d) {
            info = d
            title = "Copy an interface to another character"
            copyFrom.picked = ""
            copyTo.picked = ""
            open()
        }
        width: Math.min(520, parent ? parent.width - 48 : 520)
        message: "The second character gets the first one's addon settings and uses the same profiles. A backup is made first. Close the game before copying."
        confirmText: "Copy"
        confirmEnabled: copyFrom.picked !== "" && copyTo.picked !== "" && copyFrom.picked !== copyTo.picked
        onConfirmed: { backend.copyChar(copyFrom.picked, copyTo.picked); close() }
        Caption { text: "From" }
        Picker { id: copyFrom; model: copyDialog.info.chars }
        Caption { text: "To" }
        Picker { id: copyTo; model: copyDialog.info.chars }
    }

    Modal {
        id: exportDialog
        property var info: ({ chars: [], game: "", items: [] })
        property var off: ({})
        readonly property int picked: info.items.filter(i => !off[i.ref]).length
        function toggle(ref) {
            var next = Object.assign({}, off)
            next[ref] = !next[ref]
            off = next
        }
        function show(d) {
            info = d
            off = ({})
            title = "Save your " + d.game + " interface as a pack"
            fromChar.picked = d.chars.length === 1 ? d.chars[0].key : ""
            open()
            packName.forceActiveFocus()
        }
        width: Math.min(520, parent ? parent.width - 48 : 520)
        message: "The pack holds your addon list and the settings of those addons for one character. Others import it with this app and pick their own character."
        confirmText: "Save pack"
        confirmEnabled: fromChar.picked !== "" && picked > 0
        onConfirmed: {
            backend.exportPack(fromChar.picked, packName.text, info.items.filter(i => !off[i.ref]).map(i => i.ref).join(" "))
            close()
        }
        Field {
            id: packName
            Layout.fillWidth: true
            placeholderText: "Name, for example Healer UI"
            maximumLength: 60
            Accessible.name: "Pack name"
        }
        Caption { text: "Character to take the settings from" }
        Picker { id: fromChar; model: exportDialog.info.chars }
        Caption { text: "Addons to include" }
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, 150)
            clip: true
            model: exportDialog.info.items
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: RowLayout {
                id: inc
                required property var modelData
                readonly property bool on: !exportDialog.off[modelData.ref]
                width: ListView.view.width - 12
                height: 30
                spacing: 10
                Accessible.role: Accessible.CheckBox
                Accessible.name: modelData.name
                Accessible.checked: on
                TapHandler { onTapped: exportDialog.toggle(inc.modelData.ref) }
                Rectangle {
                    implicitWidth: 18
                    implicitHeight: 18
                    radius: 5
                    color: inc.on ? Theme.accent : "transparent"
                    border.color: inc.on ? Theme.accent : Theme.sub
                    Icon { anchors.centerIn: parent; visible: inc.on; shape: "check"; size: 12; color: Theme.onAccent }
                }
                Text {
                    Layout.fillWidth: true
                    text: inc.modelData.name
                    color: inc.on ? Theme.text : Theme.sub
                    font.pixelSize: Theme.body
                    elide: Text.ElideRight
                }
            }
        }
        Text {
            Layout.fillWidth: true
            text: "Your account, character, realm and alts are replaced with placeholders. Names of friends and guild members cannot be found automatically, so leave out addons that keep that kind of data, such as chat, friend list or damage history addons."
            color: Theme.sub
            font.pixelSize: Theme.small
            wrapMode: Text.WordWrap
        }
    }

    Modal {
        id: shareDialog
        property var items: []
        property var off: ({})
        property string game: ""
        property string link: ""
        property bool busy: false
        property bool shared: false
        readonly property int picked: items.filter(i => !off[i.ref]).length
        function show(data) {
            items = data.items
            game = data.game
            shared = data.shared
            off = ({})
            link = ""
            busy = false
            open()
            nameField.forceActiveFocus()
        }
        function toggle(ref) {
            var next = Object.assign({}, off)
            next[ref] = !next[ref]
            off = next
        }
        width: Math.min(520, parent ? parent.width - 48 : 520)
        title: link ? "Your link is ready" : "Share your " + game + " setup"
        message: link
            ? "It is on the clipboard. Anyone can paste it into Browse to install this setup. Sharing again from this install updates the same link."
            : (shared ? "This updates the link you made before. " : "") + "The app saves the list as a secret gist on your GitHub account and gives you a link to pass around."
        showCancel: !link
        confirmText: link ? "Done" : busy ? "Creating" : shared ? "Update link" : "Create link"
        confirmEnabled: link !== "" || (!busy && picked > 0)
        onConfirmed: {
            if (link) {
                close()
                return
            }
            busy = true
            backend.publishList(nameField.text, aboutField.text, items.filter(i => !off[i.ref]).map(i => i.ref).join(" "))
        }
        RowLayout {
            visible: shareDialog.link !== ""
            Layout.fillWidth: true
            spacing: 8
            Field { Layout.fillWidth: true; readOnly: true; text: shareDialog.link; Accessible.name: "Link" }
            Btn { text: "Copy"; iconName: "copy"; onClicked: backend.copyText(shareDialog.link) }
        }
        Field {
            id: nameField
            visible: !shareDialog.link
            Layout.fillWidth: true
            placeholderText: "Name, for example Raid healer"
            maximumLength: 60
            Accessible.name: "Setup name"
        }
        Field {
            id: aboutField
            visible: !shareDialog.link
            Layout.fillWidth: true
            placeholderText: "One line about it (optional)"
            maximumLength: 120
            Accessible.name: "About this setup"
        }
        ListView {
            visible: !shareDialog.link
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, 240)
            clip: true
            model: shareDialog.items
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: RowLayout {
                id: pick
                required property var modelData
                readonly property bool on: !shareDialog.off[modelData.ref]
                width: ListView.view.width - 12
                height: 30
                spacing: 10
                Accessible.role: Accessible.CheckBox
                Accessible.name: modelData.name
                Accessible.checked: on
                TapHandler { onTapped: shareDialog.toggle(pick.modelData.ref) }
                Rectangle {
                    implicitWidth: 18
                    implicitHeight: 18
                    radius: 5
                    color: pick.on ? Theme.accent : "transparent"
                    border.color: pick.on ? Theme.accent : Theme.line
                    Icon { anchors.centerIn: parent; visible: pick.on; shape: "check"; size: 12; color: Theme.onAccent }
                }
                Text {
                    Layout.fillWidth: true
                    text: pick.modelData.name
                    color: pick.on ? Theme.text : Theme.sub
                    font.pixelSize: Theme.body
                    elide: Text.ElideRight
                }
            }
        }
        Text {
            visible: !shareDialog.link
            Layout.fillWidth: true
            text: "<a href='x'>Send it to the public list instead</a>"
            textFormat: Text.StyledText
            color: Theme.sub
            linkColor: Theme.accentText
            font.pixelSize: Theme.small
            onLinkActivated: { shareDialog.close(); backend.shareList() }
        }
    }

    Modal {
        id: listDialog
        property var item: ({ refs: [], count: 0, missing: "", url: "", following: false, all: "" })
        property bool wantFollow: false
        function show(data) {
            item = data
            wantFollow = false
            title = data.name
            message = [data.by ? "by " + data.by : "", data.game, data.about].filter(s => s).join("  ·  ")
            open()
        }
        width: Math.min(520, parent ? parent.width - 48 : 520)
        confirmText: item.count === 0 ? (wantFollow ? "Follow" : "Nothing to install") : "Install " + item.count + (item.count === 1 ? " addon" : " addons") + " on " + backend.clientLabel
        confirmEnabled: (item.count > 0 || wantFollow) && backend.hasClient
        onConfirmed: {
            if (wantFollow) backend.follow(item.url, item.name, item.all)
            if (item.count > 0) backend.installList(item.missing)
            close()
        }
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, 300)
            clip: true
            spacing: 4
            model: listDialog.item.refs
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            delegate: RowLayout {
                id: refRow
                required property var modelData
                width: ListView.view.width - 12
                spacing: 8
                Text {
                    Layout.fillWidth: true
                    text: refRow.modelData.ref
                    color: refRow.modelData.have ? Theme.sub : Theme.text
                    font.pixelSize: Theme.body
                    elide: Text.ElideMiddle
                }
                Text {
                    visible: refRow.modelData.have
                    text: "installed"
                    color: Theme.sub
                    font.pixelSize: Theme.small
                }
            }
        }
        RowLayout {
            visible: listDialog.item.url !== ""
            Layout.fillWidth: true
            Layout.topMargin: 4
            spacing: 10
            Toggle {
                visible: !listDialog.item.following
                value: listDialog.wantFollow
                Accessible.name: "Follow this setup"
                onRequested: (on) => listDialog.wantFollow = on
            }
            Text {
                Layout.fillWidth: true
                text: listDialog.item.following ? "You follow this setup." : "Follow this setup, and tell me when addons are added to it or dropped"
                color: Theme.sub
                font.pixelSize: Theme.small
                wrapMode: Text.WordWrap
            }
        }
    }

    Rectangle {
        id: toast
        property bool isError: false
        property string message: ""
        function show(text, error) {
            message = text
            isError = error
            opacity = 1
            hide.interval = error ? 8000 : 3500
            hide.restart()
        }
        z: 100
        opacity: 0
        visible: opacity > 0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.horizontalCenterOffset: 118
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        width: Math.min(toastRow.implicitWidth + 32, window.width - 300)
        height: Math.max(44, toastText.implicitHeight + 24)
        radius: 12
        color: Theme.raised
        border.color: isError ? Theme.tint(Theme.err, 0.6) : Theme.line
        Behavior on opacity { NumberAnimation { duration: 160 } }
        Timer { id: hide; onTriggered: toast.opacity = 0 }
        TapHandler { onTapped: toast.opacity = 0 }
        RowLayout {
            id: toastRow
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 16
            spacing: 10
            Icon { shape: toast.isError ? "alert" : "check"; size: 17; color: toast.isError ? Theme.err : Theme.ok }
            Text {
                id: toastText
                Layout.fillWidth: true
                text: toast.message
                color: Theme.text
                font.pixelSize: Theme.body
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
            }
        }
    }
}
