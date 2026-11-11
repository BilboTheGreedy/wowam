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
                AddonsPage { id: addonsPage; onAddFolderRequested: folderDialog.open() }
                SettingsPage { onAddFolderRequested: folderDialog.open(); onTourRequested: tour.start() }
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
                text: "In Browse, search by name or paste a link from GitHub, WoWInterface, CurseForge or Wago. Any GitHub addon link works, and the addon is kept up to date from then on."
            },
            {
                title: "Shared setups",
                text: "Browse also lists whole addon setups that other players have published. Open one to see what is in it, then install the lot. Share mine publishes your own list, and a link to a list in a gist or a GitHub repo can be pasted anywhere an addon link can."
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

    Modal {
        id: listDialog
        property var item: ({ refs: [], count: 0, missing: "" })
        function show(data) {
            item = data
            title = data.name
            message = [data.by ? "by " + data.by : "", data.game, data.about].filter(s => s).join("  ·  ")
            open()
        }
        width: Math.min(520, parent ? parent.width - 48 : 520)
        confirmText: item.count === 0 ? "Nothing to install" : "Install " + item.count + (item.count === 1 ? " addon" : " addons") + " on " + backend.clientLabel
        confirmEnabled: item.count > 0 && backend.hasClient
        onConfirmed: { backend.installList(item.missing); close() }
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
