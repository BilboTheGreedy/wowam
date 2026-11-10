import QtQuick
import QtQuick.Layouts
import Wowam

Rectangle {
    id: root
    property string title: ""
    property string hint: ""
    default property alias content: body.data
    Layout.fillWidth: true
    implicitHeight: col.implicitHeight + 36
    radius: Theme.radius
    color: Theme.card
    border.color: Theme.line
    border.width: Theme.dark ? 0 : 1

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 18
        spacing: 4
        Text {
            text: root.title
            color: Theme.text
            font.pixelSize: 15
            font.weight: Font.DemiBold
        }
        Text {
            visible: root.hint !== ""
            text: root.hint
            color: Theme.sub
            font.pixelSize: Theme.small
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        ColumnLayout {
            id: body
            Layout.fillWidth: true
            Layout.topMargin: 10
            spacing: 12
        }
    }
}
