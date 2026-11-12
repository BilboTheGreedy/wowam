import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Wowam

Rectangle {
    id: root
    property alias installsItem: list
    property alias settingsItem: settingsNav
    property bool settingsOpen: false
    signal clientPicked(int index)
    signal settingsClicked()
    signal addClicked()

    color: Theme.panel

    component NavItem: Rectangle {
        id: nav
        property string label: ""
        property string iconName: ""
        property bool active: false
        signal clicked()
        Layout.fillWidth: true
        implicitHeight: 38
        radius: 8
        color: active ? Theme.accentSoft : hover.hovered ? Theme.tint(Theme.sub, 0.12) : "transparent"
        activeFocusOnTab: true
        border.width: activeFocus ? 2 : 0
        border.color: Theme.accent
        Keys.onReturnPressed: nav.clicked()
        Keys.onSpacePressed: nav.clicked()
        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: nav.clicked() }
        Row {
            x: 12
            spacing: 10
            anchors.verticalCenter: parent.verticalCenter
            Icon {
                shape: nav.iconName
                size: 17
                color: nav.active ? Theme.accentText : Theme.sub
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: nav.label
                color: nav.active ? Theme.text : Theme.sub
                font.pixelSize: Theme.body
                font.weight: Font.Medium
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 4

        RowLayout {
            Layout.topMargin: 6
            Layout.leftMargin: 6
            Layout.bottomMargin: 18
            spacing: 10
            Image {
                source: Qt.resolvedUrl("../../../data/wowam.svg")
                sourceSize.width: 34
                sourceSize.height: 34
            }
            Column {
                spacing: 1
                Text {
                    text: "WORLD OF WARCRAFT"
                    color: Theme.faint
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.1
                }
                Text {
                    text: "Addon Manager"
                    color: Theme.text
                    font.pixelSize: 16
                    font.weight: Font.Bold
                }
            }
        }

        Text {
            text: "INSTALLS"
            color: Theme.faint
            font.pixelSize: 11
            font.weight: Font.DemiBold
            font.letterSpacing: 1.1
            Layout.leftMargin: 8
            Layout.bottomMargin: 4
        }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: backend.clients
            boundsBehavior: Flickable.StopAtBounds
            delegate: Rectangle {
                id: item
                required property int index
                required property string label
                required property string location
                required property string version
                required property int updates
                readonly property bool current: !root.settingsOpen && index === backend.currentIndex
                width: list.width
                height: 54
                radius: 8
                color: current ? Theme.accentSoft : hover.hovered ? Theme.tint(Theme.sub, 0.12) : "transparent"
                activeFocusOnTab: true
                border.width: activeFocus ? 2 : 0
                border.color: Theme.accent
                Keys.onReturnPressed: root.clientPicked(index)
                Keys.onSpacePressed: root.clientPicked(index)
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: root.clientPicked(item.index) }

                Rectangle {
                    visible: item.current
                    width: 3
                    height: 22
                    radius: 2
                    color: Theme.accent
                    anchors.verticalCenter: parent.verticalCenter
                }
                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: 14
                    anchors.right: badge.visible ? badge.left : parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Text {
                        width: parent.width
                        text: item.label
                        color: Theme.text
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        width: parent.width
                        text: item.location + (item.version ? "  ·  " + item.version.split(".").slice(0, 3).join(".") : "")
                        color: Theme.sub
                        font.pixelSize: Theme.small
                        elide: Text.ElideRight
                    }
                }
                Rectangle {
                    id: badge
                    visible: item.updates > 0
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.max(22, count.implicitWidth + 12)
                    height: 22
                    radius: 11
                    color: Theme.accent
                    Text {
                        id: count
                        anchors.centerIn: parent
                        text: item.updates
                        color: Theme.onAccent
                        font.pixelSize: 11
                        font.weight: Font.Bold
                    }
                }
            }
        }

        NavItem { label: "Add WoW folder"; iconName: "plus"; onClicked: root.addClicked() }
        NavItem { id: settingsNav; label: "Settings"; iconName: "settings"; active: root.settingsOpen; onClicked: root.settingsClicked() }
    }
}
