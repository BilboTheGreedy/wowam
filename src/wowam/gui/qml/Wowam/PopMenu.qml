import QtQuick
import QtQuick.Controls.Basic
import Wowam

Menu {
    id: root
    padding: 6
    implicitWidth: 220
    background: Rectangle {
        implicitWidth: 220
        radius: 10
        color: Theme.raised
        border.color: Theme.line
    }
    delegate: PopItem {}
}
