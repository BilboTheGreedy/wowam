import QtQuick
import QtQuick.Controls.Basic
import Wowam

MenuItem {
    id: root
    property string iconName: ""
    property bool danger: false
    implicitHeight: visible ? 34 : 0
    implicitWidth: 208
    padding: 0
    font.pixelSize: Theme.body
    HoverHandler { cursorShape: Qt.PointingHandCursor }
    contentItem: Item {
        Icon {
            id: glyph
            x: 10
            anchors.verticalCenter: parent.verticalCenter
            shape: root.checked ? "check" : root.iconName
            size: 16
            color: root.danger ? Theme.err : root.checked ? Theme.accentText : Theme.sub
        }
        Text {
            x: 36
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            font: root.font
            color: !root.enabled ? Theme.faint : root.danger ? Theme.err : Theme.text
        }
    }
    indicator: Item {}
    arrow: Item {}
    background: Rectangle {
        radius: 6
        color: root.highlighted ? Theme.tint(root.danger ? Theme.err : Theme.sub, 0.16) : "transparent"
    }
}
