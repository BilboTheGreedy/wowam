import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Wowam

Item {
    id: root
    property int tab: 0
    signal addFolderRequested()

    function clientChanged() {
        if (browseField.text.trim().length > 0) backend.search(browseField.text)
    }

    function focusSearch() {
        if (tab === 0) filterField.forceActiveFocus()
        else browseField.forceActiveFocus()
    }

    function browseFor(text) {
        tab = 1
        browseField.text = text
        backend.search(text)
    }

    component TabButton: Item {
        id: tb
        property string label: ""
        property bool active: false
        property int badge: 0
        signal clicked()
        implicitWidth: tabRow.implicitWidth + 8
        implicitHeight: 40
        activeFocusOnTab: true
        Keys.onReturnPressed: tb.clicked()
        Keys.onSpacePressed: tb.clicked()
        HoverHandler { id: tbHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: tb.clicked() }
        Row {
            id: tabRow
            anchors.centerIn: parent
            spacing: 7
            Text {
                text: tb.label
                color: tb.active ? Theme.text : tbHover.hovered || tb.activeFocus ? Theme.text : Theme.sub
                font.pixelSize: 14
                font.weight: tb.active ? Font.DemiBold : Font.Medium
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                visible: tb.badge > 0
                width: Math.max(20, tbCount.implicitWidth + 10)
                height: 18
                radius: 9
                color: Theme.tint(Theme.sub, 0.18)
                anchors.verticalCenter: parent.verticalCenter
                Text { id: tbCount; anchors.centerIn: parent; text: tb.badge; color: Theme.sub; font.pixelSize: 11; font.weight: Font.DemiBold }
            }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 2
            radius: 1
            color: tb.active ? Theme.accent : "transparent"
        }
    }

    component Empty: ColumnLayout {
        property string iconName: "archive"
        property string heading: ""
        property string detail: ""
        default property alias extra: slot.data
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 440)
        spacing: 8
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 56
            Layout.preferredHeight: 56
            radius: 16
            color: Theme.tint(Theme.sub, 0.12)
            Icon { anchors.centerIn: parent; shape: parent.parent.iconName; size: 26; color: Theme.sub }
        }
        Text {
            Layout.topMargin: 8
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: parent.heading
            color: Theme.text
            font.pixelSize: 16
            font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: parent.detail
            visible: text !== ""
            color: Theme.sub
            font.pixelSize: Theme.body
            lineHeight: 1.3
            wrapMode: Text.WordWrap
        }
        RowLayout {
            id: slot
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 10
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 24
        anchors.bottomMargin: 0
        spacing: 0
        visible: backend.hasClient

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Text {
                    text: backend.clientLabel
                    color: Theme.text
                    font.pixelSize: Theme.title
                    font.weight: Font.Bold
                }
                Text {
                    Layout.fillWidth: true
                    text: {
                        if (backend.loading) return "Reading addon folder"
                        if (backend.addonCount === 0) return "No addons installed"
                        var s = backend.addonCount + (backend.addonCount === 1 ? " addon" : " addons")
                        if (backend.checking) return s + "  ·  checking for updates"
                        if (backend.updateCount > 0) return s + "  ·  " + backend.updateCount + (backend.updateCount === 1 ? " update ready" : " updates ready")
                        return s + "  ·  everything is up to date"
                    }
                    color: Theme.sub
                    font.pixelSize: Theme.body
                    elide: Text.ElideRight
                }
            }
            IconBtn {
                iconName: "refresh"
                tip: "Check again"
                spinning: backend.checking
                enabled: !backend.working
                Accessible.name: "Check for updates"
                onClicked: backend.refresh()
            }
            Btn {
                kind: "primary"
                iconName: "download"
                visible: backend.updateCount > 0
                enabled: !backend.working
                text: backend.updateCount === 1 ? "Update 1 addon" : "Update all " + backend.updateCount
                onClicked: backend.updateAll()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 16
            spacing: 18
            TabButton { label: "Installed"; active: root.tab === 0; badge: backend.addonCount; onClicked: root.tab = 0 }
            TabButton { label: "Browse"; active: root.tab === 1; onClicked: { root.tab = 1; browseField.forceActiveFocus() } }
            Item { Layout.fillWidth: true }
            Field {
                id: filterField
                visible: root.tab === 0
                Layout.preferredWidth: 240
                iconName: "search"
                placeholderText: "Filter installed"
                Accessible.name: "Filter installed addons"
                onTextChanged: backend.setFilter(text)
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.tab

            Item {
                ListView {
                    id: list
                    anchors.fill: parent
                    topMargin: 14
                    bottomMargin: 20
                    spacing: 6
                    clip: true
                    model: backend.addons
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: AddonRow {
                        width: list.width - (list.ScrollBar.vertical.visible ? 12 : 0)
                        onMenuRequested: (row, anchor) => {
                            menu.row = row
                            menu.popup(anchor, 0, anchor.height + 4)
                        }
                        onLinkRequested: (row) => linkDialog.show(row)
                        onFindRequested: (name) => root.browseFor(name)
                    }
                }
                Empty {
                    visible: list.count === 0 && !backend.loading && backend.addonCount === 0
                    heading: "No addons here yet"
                    detail: "Find addons in Browse, or paste a link from GitHub or WoWInterface."
                    Btn { text: "Browse addons"; kind: "primary"; onClicked: { root.tab = 1; browseField.forceActiveFocus() } }
                }
                Empty {
                    visible: list.count === 0 && !backend.loading && backend.addonCount > 0
                    iconName: "search"
                    heading: "Nothing matches that filter"
                    Btn { text: "Clear filter"; onClicked: filterField.text = "" }
                }
            }

            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 14
                        spacing: 8
                        Field {
                            id: browseField
                            Layout.fillWidth: true
                            implicitHeight: 42
                            iconName: "search"
                            placeholderText: "Search addons, or paste a GitHub, WoWInterface or Wago link"
                            Accessible.name: "Search addons"
                            onAccepted: { debounce.stop(); backend.search(text) }
                            onTextChanged: debounce.restart()
                            Timer {
                                id: debounce
                                interval: 500
                                onTriggered: if (browseField.text.trim().length === 0 || browseField.text.trim().length > 2) backend.search(browseField.text)
                            }
                        }
                        Btn {
                            implicitHeight: 42
                            kind: "primary"
                            text: "Search"
                            enabled: browseField.text.trim().length > 0
                            onClicked: { debounce.stop(); backend.search(browseField.text) }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 12
                        spacing: 10
                        Toggle {
                            id: listedToggle
                            value: backend.listedOnly
                            Accessible.name: "Only addons listed for " + backend.clientLabel
                            onRequested: (on) => backend.setListedOnly(on)
                        }
                        Text {
                            text: "Only addons listed for " + backend.clientLabel
                            color: Theme.text
                            font.pixelSize: Theme.body
                            TapHandler { onTapped: backend.setListedOnly(!backend.listedOnly) }
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: backend.hiddenResults > 0
                            text: backend.hiddenResults + (backend.hiddenResults === 1 ? " result hidden" : " results hidden")
                            color: Theme.sub
                            font.pixelSize: Theme.small
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ListView {
                            id: results
                            anchors.fill: parent
                            topMargin: 12
                            bottomMargin: 20
                            spacing: 6
                            clip: true
                            model: backend.browse
                            boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            opacity: backend.searching ? 0.4 : 1
                            delegate: BrowseRow { width: results.width - (results.ScrollBar.vertical.visible ? 12 : 0) }
                        }
                        Empty {
                            visible: results.count === 0 && !backend.searching && !backend.searched
                            iconName: "globe"
                            heading: "Add an addon to " + backend.clientLabel
                            detail: "Search covers GitHub, WoWInterface and Tukui" + (backend.wagoKey ? ", plus Wago Addons." : ".") + " You can also paste an addon link, for example github.com/BigWigsMods/BigWigs."
                        }
                        Empty {
                            visible: results.count === 0 && !backend.searching && backend.searched && backend.hiddenResults === 0
                            iconName: "search"
                            heading: "No addons found"
                            detail: "Try a shorter name, or paste the addon's GitHub link."
                        }
                        Empty {
                            visible: results.count === 0 && !backend.searching && backend.searched && backend.hiddenResults > 0
                            iconName: "search"
                            heading: "Nothing is listed for " + backend.clientLabel
                            detail: backend.hiddenResults + (backend.hiddenResults === 1 ? " result is" : " results are") + " hidden because the author has not marked " + (backend.hiddenResults === 1 ? "it" : "them") + " as working with " + backend.clientLabel + "."
                            Btn { text: "Show all results"; onClicked: backend.setListedOnly(false) }
                        }
                        Row {
                            visible: backend.searching && results.count === 0
                            anchors.centerIn: parent
                            spacing: 10
                            Spinner { size: 18; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "Searching"; color: Theme.sub; font.pixelSize: Theme.body; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                }
            }
        }
    }

    Empty {
        visible: !backend.hasClient
        iconName: "folder"
        heading: "No World of Warcraft install found"
        detail: "The usual install locations are checked automatically. If your game lives somewhere else, point to its folder."
        Btn { text: "Add WoW folder"; kind: "primary"; iconName: "plus"; onClicked: root.addFolderRequested() }
    }

    PopMenu {
        id: menu
        property var row: null
        readonly property bool managed: row ? row.managed : false
        PopItem {
            text: "What's new"
            iconName: "notes"
            visible: menu.row ? menu.row.notes : false
            onTriggered: notesDialog.show(menu.row.key)
        }
        PopItem {
            text: menu.row && menu.row.previous ? "Go back to " + menu.row.previous : ""
            iconName: "back"
            visible: menu.row ? menu.row.previous !== "" : false
            onTriggered: backend.rollback(menu.row.key)
        }
        PopItem {
            text: "Reinstall"
            iconName: "download"
            visible: menu.managed
            onTriggered: backend.reinstall(menu.row.key)
        }
        PopItem {
            text: menu.row && menu.row.pinned ? "Unpin" : "Pin this version"
            iconName: "pin"
            visible: menu.managed
            onTriggered: backend.togglePin(menu.row.key)
        }
        PopItem {
            text: "Include beta releases"
            iconName: ""
            visible: menu.managed
            checked: menu.row ? menu.row.channel === "beta" : false
            onTriggered: backend.setChannel(menu.row.key, menu.row.channel === "beta" ? "stable" : "beta")
        }
        PopItem {
            text: "Open web page"
            iconName: "external"
            visible: menu.row ? menu.row.page !== "" : false
            onTriggered: backend.openUrl(menu.row.page)
        }
        PopItem {
            text: "Open folder"
            iconName: "folder"
            onTriggered: backend.openFolder(menu.row.key)
        }
        PopItem {
            text: menu.managed ? "Change source" : "Set source"
            iconName: "link"
            onTriggered: linkDialog.show(menu.row)
        }
        PopItem {
            text: "Forget source"
            iconName: "close"
            visible: menu.managed
            onTriggered: backend.forget(menu.row.key)
        }
        PopItem {
            text: "Remove"
            iconName: "trash"
            danger: true
            onTriggered: removeDialog.show(menu.row)
        }
    }

    Modal {
        id: removeDialog
        property string key: ""
        function show(row) {
            key = row.key
            title = "Remove " + row.name + "?"
            message = (row.folders > 1 ? "This deletes its " + row.folders + " folders" : "This deletes its folder")
                + " from " + backend.clientLabel + ". Your saved settings for the addon stay in place."
            open()
        }
        confirmText: "Remove"
        danger: true
        onConfirmed: { backend.removeAddon(key); close() }
    }

    Modal {
        id: notesDialog
        property string body: ""
        property bool markdown: false
        function show(key) {
            var n = backend.notesFor(key)
            title = n.title
            body = n.text
            markdown = n.markdown
            open()
        }
        width: Math.min(620, parent ? parent.width - 48 : 620)
        confirmText: "Close"
        showCancel: false
        onConfirmed: close()
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(notesText.implicitHeight, 380)
            clip: true
            contentWidth: availableWidth
            Text {
                id: notesText
                width: parent.width
                text: notesDialog.body
                textFormat: notesDialog.markdown ? Text.MarkdownText : Text.PlainText
                color: Theme.text
                linkColor: Theme.accentText
                font.pixelSize: Theme.body
                lineHeight: 1.25
                wrapMode: Text.Wrap
                onLinkActivated: (link) => backend.openUrl(link)
            }
        }
    }

    Modal {
        id: linkDialog
        property string key: ""
        function show(row) {
            key = row.key
            title = "Where does " + row.name + " come from?"
            linkField.text = ""
            open()
            linkField.forceActiveFocus()
        }
        message: "Paste the addon's page on GitHub, WoWInterface or Wago Addons. That page is then checked for new versions."
        confirmText: "Set source"
        confirmEnabled: linkField.text.trim().length > 0
        onConfirmed: if (backend.linkAddon(key, linkField.text)) close()
        Field {
            id: linkField
            Layout.fillWidth: true
            placeholderText: "https://github.com/owner/addon"
            Accessible.name: "Addon page link"
            onAccepted: if (linkDialog.confirmEnabled) linkDialog.confirmed()
        }
    }
}
