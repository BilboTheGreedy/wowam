import QtQuick
import QtQuick.Controls.Basic
import Wowam

Button {
    id: root
    property string iconName: ""
    property string tip: ""
    property bool spinning: false
    implicitWidth: 34
    implicitHeight: 34
    padding: 0
    hoverEnabled: true

    HoverHandler { cursorShape: Qt.PointingHandCursor }

    contentItem: Item {
        Icon {
            id: glyph
            anchors.centerIn: parent
            shape: root.iconName
            color: root.enabled ? (root.hovered ? Theme.text : Theme.sub) : Theme.faint
            RotationAnimator on rotation {
                running: root.spinning
                from: 0
                to: 360
                duration: 900
                loops: Animation.Infinite
            }
        }
    }

    background: Rectangle {
        radius: 8
        color: root.hovered || root.down ? Theme.tint(Theme.sub, 0.16) : "transparent"
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
    }

    ToolTip {
        visible: root.tip !== "" && root.hovered
        delay: 600
        text: root.tip
        contentItem: Text { text: root.tip; color: Theme.text; font.pixelSize: Theme.small }
        background: Rectangle { color: Theme.raised; radius: 6; border.color: Theme.line }
    }
}
