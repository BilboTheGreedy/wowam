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
    visible: true
    title: "wowam"
    color: Theme.bg

    property bool settingsOpen: false

    Component.onCompleted: Theme.mode = backend.themeMode

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
                            ? "Downloading wowam " + backend.updateVersion + "  ·  " + Math.round(backend.updateProgress * 100) + "%"
                            : "wowam " + backend.updateVersion + " is available. You have " + backend.version + "."
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
                SettingsPage { onAddFolderRequested: folderDialog.open() }
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
        function onShowBrowse(text) {
            window.settingsOpen = false
            addonsPage.browseFor(text)
            window.raise()
            window.requestActivate()
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
