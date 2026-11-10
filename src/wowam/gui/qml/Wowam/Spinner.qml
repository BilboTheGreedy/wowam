import QtQuick
import Wowam

Item {
    id: root
    property int size: 14
    property color color: Theme.sub
    width: size
    height: size
    Icon {
        anchors.centerIn: parent
        shape: "refresh"
        size: root.size
        color: root.color
        RotationAnimator on rotation {
            running: root.visible
            from: 0
            to: 360
            duration: 900
            loops: Animation.Infinite
        }
    }
}
