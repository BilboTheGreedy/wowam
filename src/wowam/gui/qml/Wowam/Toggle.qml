import QtQuick
import QtQuick.Controls.Basic
import Wowam

Switch {
    id: root
    property bool value: false
    signal requested(bool on)
    checked: value
    onToggled: {
        var want = checked
        checked = Qt.binding(function() { return root.value })
        root.requested(want)
    }
    implicitWidth: 42
    implicitHeight: 24
    padding: 0
    HoverHandler { cursorShape: Qt.PointingHandCursor }
    indicator: Rectangle {
        width: 42
        height: 24
        radius: 12
        color: root.checked ? Theme.accent : Theme.tint(Theme.sub, 0.3)
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.text
        Behavior on color { ColorAnimation { duration: 120 } }
        Rectangle {
            width: 18
            height: 18
            radius: 9
            y: 3
            x: root.checked ? 21 : 3
            color: root.checked ? Theme.onAccent : "#ffffff"
            Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        }
    }
    contentItem: Item {}
}
