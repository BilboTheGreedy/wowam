import QtQuick
import QtQuick.Controls.Basic
import Wowam

Button {
    id: root
    property string kind: "soft"
    property string iconName: ""
    readonly property color fg: !enabled ? Theme.faint
        : kind === "primary" ? Theme.onAccent
        : kind === "danger" ? Theme.err
        : kind === "accent" ? Theme.accentText
        : Theme.text

    implicitHeight: 34
    implicitWidth: row.implicitWidth + 28
    padding: 0
    font.pixelSize: Theme.body
    font.weight: Font.DemiBold
    hoverEnabled: true

    HoverHandler { cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }

    contentItem: Item {
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 7
            Icon {
                visible: root.iconName !== ""
                shape: root.iconName
                size: 16
                color: root.fg
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                visible: root.text !== ""
                text: root.text
                font: root.font
                color: root.fg
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    background: Rectangle {
        radius: 8
        color: {
            if (!root.enabled) return Theme.tint(Theme.sub, 0.08)
            if (root.kind === "primary") return root.down ? Qt.darker(Theme.accent, 1.15) : root.hovered ? Qt.lighter(Theme.accent, 1.08) : Theme.accent
            if (root.kind === "accent") return root.hovered ? Theme.tint(Theme.accent, 0.26) : Theme.accentSoft
            if (root.kind === "danger") return root.hovered ? Theme.tint(Theme.err, 0.2) : Theme.tint(Theme.err, 0.1)
            if (root.kind === "ghost") return root.hovered ? Theme.tint(Theme.sub, 0.14) : "transparent"
            return root.hovered ? Theme.tint(Theme.sub, 0.22) : Theme.tint(Theme.sub, 0.12)
        }
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
    }
}
