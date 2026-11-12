import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Wowam

Rectangle {
    id: root
    required property int index
    required property string key
    required property string name
    required property string version
    required property string latest
    required property string source
    required property string status
    required property string statusText
    required property bool pinned
    required property bool managed
    required property double progress
    required property string author
    required property string page
    required property string channel
    required property string action
    required property int folders
    required property bool busy
    required property string previous
    required property bool notes
    required property bool outdated
    required property string needs
    required property bool off
    required property string memo
    required property string stale

    signal menuRequested(var row, var anchor)
    signal linkRequested(var row)
    signal findRequested(string name)

    height: 64
    radius: Theme.radius
    color: hover.hovered ? Theme.cardHover : Theme.card
    border.color: Theme.line
    border.width: Theme.dark ? 0 : 1

    HoverHandler { id: hover }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 10
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
            RowLayout {
                spacing: 6
                Text {
                    text: root.name
                    color: Theme.text
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    Layout.maximumWidth: implicitWidth + 1
                }
                Icon { visible: root.pinned; shape: "pin"; size: 14; color: Theme.warn }
                Rectangle {
                    visible: root.channel === "beta"
                    implicitWidth: beta.implicitWidth + 10
                    implicitHeight: 16
                    radius: 4
                    color: Theme.tint(Theme.warn, 0.16)
                    Text { id: beta; anchors.centerIn: parent; text: "BETA"; color: Theme.warn; font.pixelSize: 9; font.weight: Font.Bold }
                }
                Rectangle {
                    visible: root.outdated
                    implicitWidth: old.implicitWidth + 10
                    implicitHeight: 16
                    radius: 4
                    color: Theme.tint(Theme.sub, 0.16)
                    Text { id: old; anchors.centerIn: parent; text: "OUT OF DATE"; color: Theme.sub; font.pixelSize: 9; font.weight: Font.Bold }
                }
                Rectangle {
                    visible: root.stale !== ""
                    implicitWidth: staleText.implicitWidth + 10
                    implicitHeight: 16
                    radius: 4
                    color: Theme.tint(Theme.sub, 0.16)
                    Text { id: staleText; anchors.centerIn: parent; text: "NO UPDATE SINCE " + root.stale; color: Theme.sub; font.pixelSize: 9; font.weight: Font.Bold }
                }
                Item { Layout.fillWidth: true }
            }
            Text {
                text: {
                    var parts = []
                    if (root.version) parts.push(root.version)
                    if (root.author) parts.push(root.author)
                    if (root.folders > 1) parts.push(root.folders + " folders")
                    if (root.memo) parts.push("note: " + root.memo)
                    return parts.join("  ·  ")
                }
                color: Theme.sub
                font.pixelSize: Theme.small
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        Rectangle {
            visible: root.width > 760
            Layout.preferredWidth: 104
            Layout.preferredHeight: 24
            color: "transparent"
            Rectangle {
                visible: root.source !== ""
                anchors.verticalCenter: parent.verticalCenter
                width: chip.implicitWidth + 16
                height: 22
                radius: 6
                color: Theme.tint(Theme.sub, 0.13)
                Text { id: chip; anchors.centerIn: parent; text: root.source; color: Theme.sub; font.pixelSize: 11; font.weight: Font.Medium }
            }
        }

        RowLayout {
            Layout.preferredWidth: Math.max(150, Math.min(260, root.width * 0.26))
            Layout.maximumWidth: Layout.preferredWidth
            spacing: 8
            Spinner {
                visible: root.status === "checking" || root.status === "working"
                size: 14
                color: root.status === "working" ? Theme.accentText : Theme.sub
            }
            Rectangle {
                visible: !(root.status === "checking" || root.status === "working")
                Layout.preferredWidth: 8
                Layout.preferredHeight: 8
                radius: 4
                color: root.status === "unknown" ? "transparent" : Theme.statusColor(root.status)
                border.width: root.status === "unknown" ? 1.5 : 0
                border.color: Theme.faint
            }
            Text {
                id: statusLabel
                text: root.statusText
                color: root.status === "ok" || root.status === "unknown" || root.status === "checking" ? Theme.sub : Theme.statusColor(root.status)
                font.pixelSize: Theme.small
                font.weight: root.status === "update" ? Font.DemiBold : Font.Normal
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                HoverHandler { id: statusHover }
                ToolTip {
                    visible: statusHover.hovered && statusLabel.truncated
                    delay: 400
                    contentItem: Text { text: root.statusText; color: Theme.text; font.pixelSize: Theme.small; wrapMode: Text.WordWrap; width: Math.min(implicitWidth, 360) }
                    background: Rectangle { color: Theme.raised; radius: 6; border.color: Theme.line }
                }
            }
        }

        Item {
            Layout.preferredWidth: 104
            Layout.preferredHeight: 34
            Btn {
                anchors.right: parent.right
                visible: root.action !== "" && !root.busy
                kind: root.action === "update" ? "primary" : root.action === "accept" ? "accent" : "soft"
                text: root.action === "update" ? "Update"
                    : root.action === "accept" ? "Use this"
                    : root.action === "link" ? "Set source"
                    : root.action === "reinstall" ? "Reinstall"
                    : root.action === "find" ? "Find it"
                    : root.action === "enable" ? "Turn on"
                    : "Retry"
                onClicked: {
                    if (root.action === "update") backend.updateAddon(root.key)
                    else if (root.action === "accept") backend.acceptGuess(root.key)
                    else if (root.action === "link") root.linkRequested(root)
                    else if (root.action === "reinstall") backend.reinstall(root.key)
                    else if (root.action === "find") root.findRequested(root.needs)
                    else if (root.action === "enable") backend.setEnabled(root.key, true)
                    else backend.retry(root.key)
                }
            }
        }

        IconBtn {
            id: more
            iconName: "more"
            tip: "More"
            enabled: !root.busy
            Accessible.name: "More actions for " + root.name
            onClicked: root.menuRequested(root, more)
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
        Behavior on width { NumberAnimation { duration: 120 } }
    }
}
