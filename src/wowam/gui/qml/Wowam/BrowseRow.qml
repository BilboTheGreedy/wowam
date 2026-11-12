import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Wowam

Rectangle {
    id: root
    required property string key
    required property string name
    required property string author
    required property string version
    required property string source
    required property string summary
    required property string listed
    required property string page
    required property bool installed
    required property bool busy
    required property double progress

    height: 64
    radius: Theme.radius
    color: hover.hovered ? Theme.cardHover : Theme.card
    border.color: Theme.line
    border.width: Theme.dark ? 0 : 1

    HoverHandler { id: hover }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 12
        spacing: 14

        Rectangle {
            Layout.preferredWidth: 38
            Layout.preferredHeight: 38
            radius: 10
            color: Theme.tint(Theme.avatar(root.name), Theme.dark ? 0.2 : 0.14)
            Text {
                anchors.centerIn: parent
                text: root.name.replace(/^[^A-Za-z0-9]+/, "").charAt(0).toUpperCase()
                color: Theme.avatar(root.name)
                font.pixelSize: 17
                font.weight: Font.Bold
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 120
            Layout.preferredWidth: 200
            spacing: 3
            Text {
                text: root.name
                color: Theme.text
                font.pixelSize: 14
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Text {
                text: {
                    var parts = []
                    if (root.author) parts.push(root.author)
                    if (root.version) parts.push(root.version)
                    if (root.summary) parts.push(root.summary)
                    return parts.join("  ·  ")
                }
                color: Theme.sub
                font.pixelSize: Theme.small
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        Row {
            visible: (root.listed === "yes" || root.listed === "no") && !root.installed && root.width > 640
            spacing: 5
            Icon {
                visible: root.listed === "yes"
                shape: "check"
                size: 14
                color: Theme.ok
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: (root.listed === "yes" ? "Listed for " : "Not listed for ") + backend.clientLabel
                color: root.listed === "yes" ? Theme.ok : Theme.warn
                font.pixelSize: Theme.small
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Rectangle {
            Layout.preferredWidth: chip.implicitWidth + 16
            Layout.preferredHeight: 22
            radius: 6
            color: Theme.tint(Theme.sub, 0.13)
            Text { id: chip; anchors.centerIn: parent; text: root.source; color: Theme.sub; font.pixelSize: 11; font.weight: Font.Medium }
        }

        IconBtn {
            iconName: "notes"
            tip: "Read about it"
            Accessible.name: "Read about " + root.name
            onClicked: backend.openAbout(root.key, root.name)
        }

        IconBtn {
            iconName: "external"
            tip: "Open web page"
            visible: root.page !== ""
            Accessible.name: "Open web page for " + root.name
            onClicked: backend.openUrl(root.page)
        }

        Item {
            Layout.preferredWidth: 104
            Layout.preferredHeight: 34
            Btn {
                anchors.right: parent.right
                visible: !root.busy
                enabled: !root.installed
                kind: root.installed ? "soft" : "primary"
                iconName: root.installed ? "check" : ""
                text: root.installed ? "Installed" : "Install"
                onClicked: backend.installRef(root.key)
            }
            Row {
                visible: root.busy
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                Spinner { color: Theme.accentText; anchors.verticalCenter: parent.verticalCenter }
                Text { text: "Installing"; color: Theme.accentText; font.pixelSize: Theme.small; anchors.verticalCenter: parent.verticalCenter }
            }
        }
    }

    Rectangle {
        visible: root.busy && root.progress > 0
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.leftMargin: 10
        height: 3
        radius: 1.5
        width: (parent.width - 20) * root.progress
        color: Theme.accent
    }
}
