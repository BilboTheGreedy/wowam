import QtQuick
import QtQuick.Controls.Basic
import Wowam

TextField {
    id: root
    property string iconName: ""
    implicitHeight: 36
    leftPadding: iconName ? 36 : 12
    rightPadding: 12
    topPadding: 0
    bottomPadding: 0
    verticalAlignment: TextInput.AlignVCenter
    font.pixelSize: Theme.body
    color: Theme.text
    placeholderTextColor: Theme.faint
    selectionColor: Theme.accent
    selectedTextColor: Theme.onAccent
    selectByMouse: true

    background: Rectangle {
        radius: 8
        color: Theme.dark ? Theme.tint(Theme.sub, 0.1) : "#ffffff"
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? Theme.accent : Theme.line
        Icon {
            visible: root.iconName !== ""
            shape: root.iconName
            size: 16
            x: 11
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.faint
        }
    }
}
