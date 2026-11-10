import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Wowam

Popup {
    id: root
    property string title: ""
    property string message: ""
    property string confirmText: "OK"
    property bool danger: false
    property bool confirmEnabled: true
    default property alias extra: slot.data
    signal confirmed()

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(460, parent ? parent.width - 48 : 460)
    modal: true
    focus: true
    padding: 22
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, Theme.dark ? 0.55 : 0.3) }

    background: Rectangle {
        radius: 14
        color: Theme.raised
        border.color: Theme.line
    }

    contentItem: ColumnLayout {
        spacing: 10
        Text {
            text: root.title
            color: Theme.text
            font.pixelSize: 17
            font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Text {
            visible: root.message !== ""
            text: root.message
            color: Theme.sub
            font.pixelSize: Theme.body
            lineHeight: 1.25
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        ColumnLayout {
            id: slot
            Layout.fillWidth: true
            Layout.topMargin: 4
            spacing: 8
        }
        RowLayout {
            Layout.topMargin: 10
            Layout.fillWidth: true
            spacing: 8
            Item { Layout.fillWidth: true }
            Btn { text: "Cancel"; kind: "ghost"; onClicked: root.close() }
            Btn {
                text: root.confirmText
                kind: root.danger ? "danger" : "primary"
                enabled: root.confirmEnabled
                onClicked: root.confirmed()
            }
        }
    }
}
