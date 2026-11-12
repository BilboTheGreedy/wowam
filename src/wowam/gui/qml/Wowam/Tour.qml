import QtQuick
import QtQuick.Layouts
import Wowam

Item {
    id: root
    anchors.fill: parent
    visible: false
    z: 500
    property var steps: []
    property int step: 0
    property rect hole: Qt.rect(0, 0, 0, 0)
    property bool hasHole: false
    readonly property color shade: Qt.rgba(0, 0, 0, Theme.dark ? 0.66 : 0.45)
    signal finished()

    function start() {
        step = 0
        hasHole = false
        visible = true
        forceActiveFocus()
        show()
    }
    function stop() {
        if (!visible) return
        visible = false
        finished()
    }
    function next() {
        if (step < steps.length - 1) {
            step += 1
            show()
        } else {
            stop()
        }
    }
    function back() {
        if (step > 0) {
            step -= 1
            show()
        }
    }
    function show() {
        var s = steps[step]
        if (s.prepare) s.prepare()
        settle.restart()
    }
    function measure() {
        var s = steps[step]
        if (s.reveal) s.reveal()
        var t = s.target ? s.target() : null
        if (!t || !t.visible || t.width <= 0 || t.height <= 0) {
            hasHole = false
            return
        }
        var p = t.mapToItem(root, 0, 0)
        var pad = 6
        var x = Math.max(4, p.x - pad)
        var y = Math.max(4, p.y - pad)
        var w = Math.min(root.width - 4, p.x + t.width + pad) - x
        var h = Math.min(root.height - 4, p.y + t.height + pad) - y
        if (w <= 0 || h <= 0) {
            hasHole = false
            return
        }
        hole = Qt.rect(x, y, w, h)
        hasHole = true
    }

    Timer { id: settle; interval: 90; onTriggered: root.measure() }
    onWidthChanged: if (visible) settle.restart()
    onHeightChanged: if (visible) settle.restart()

    Keys.onEscapePressed: stop()
    Keys.onReturnPressed: next()
    Keys.onRightPressed: next()
    Keys.onLeftPressed: back()

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.AllButtons
        onWheel: (wheel) => wheel.accepted = true
    }

    Rectangle { visible: !root.hasHole; anchors.fill: parent; color: root.shade }
    Rectangle { visible: root.hasHole; x: 0; y: 0; width: root.width; height: root.hole.y; color: root.shade }
    Rectangle {
        visible: root.hasHole
        x: 0
        y: root.hole.y + root.hole.height
        width: root.width
        height: Math.max(0, root.height - y)
        color: root.shade
    }
    Rectangle { visible: root.hasHole; x: 0; y: root.hole.y; width: root.hole.x; height: root.hole.height; color: root.shade }
    Rectangle {
        visible: root.hasHole
        x: root.hole.x + root.hole.width
        y: root.hole.y
        width: Math.max(0, root.width - x)
        height: root.hole.height
        color: root.shade
    }
    Rectangle {
        visible: root.hasHole
        x: root.hole.x - 1
        y: root.hole.y - 1
        width: root.hole.width + 2
        height: root.hole.height + 2
        radius: 10
        color: "transparent"
        border.color: Theme.accent
        border.width: 2
    }

    Rectangle {
        id: arrow
        readonly property real cx: Math.max(card.x + 24, Math.min(card.x + card.width - 24, root.hole.x + root.hole.width / 2))
        readonly property real cy: Math.max(card.y + 24, Math.min(card.y + card.height - 24, root.hole.y + Math.min(root.hole.height / 2, 40)))
        visible: root.hasHole && card.side !== "inside"
        width: 16
        height: 16
        rotation: 45
        color: Theme.raised
        border.color: Theme.line
        x: (card.side === "right" ? card.x : card.side === "left" ? card.x + card.width : cx) - 8
        y: (card.side === "below" ? card.y : card.side === "above" ? card.y + card.height : cy) - 8
    }

    Rectangle {
        id: card
        readonly property real gap: 18
        readonly property real margin: 14
        readonly property string side: {
            if (!root.hasHole) return "center"
            var h = root.hole
            if (root.width - (h.x + h.width) >= width + gap + margin) return "right"
            if (root.height - (h.y + h.height) >= height + gap + margin) return "below"
            if (h.y >= height + gap + margin) return "above"
            if (h.x >= width + gap + margin) return "left"
            return "inside"
        }
        function clampX(v) { return Math.max(margin, Math.min(root.width - width - margin, v)) }
        function clampY(v) { return Math.max(margin, Math.min(root.height - height - margin, v)) }
        width: Math.min(380, root.width - 2 * margin)
        height: body.implicitHeight + 40
        radius: 14
        color: Theme.raised
        border.color: Theme.line
        x: {
            var h = root.hole
            if (side === "right") return h.x + h.width + gap
            if (side === "left") return h.x - width - gap
            if (side === "below" || side === "above") return clampX(h.x + h.width / 2 - width / 2)
            if (side === "inside") return clampX(h.x + h.width - width - 22)
            return (root.width - width) / 2
        }
        y: {
            var h = root.hole
            if (side === "below") return h.y + h.height + gap
            if (side === "above") return h.y - height - gap
            if (side === "right" || side === "left") return clampY(h.y)
            if (side === "inside") return clampY(h.y + h.height - height - 22)
            return (root.height - height) / 2
        }
        Behavior on x { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        Behavior on y { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        ColumnLayout {
            id: body
            x: 20
            y: 20
            width: parent.width - 40
            spacing: 8
            Text {
                text: (root.step + 1) + " of " + root.steps.length
                color: Theme.sub
                font.pixelSize: Theme.small
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: root.steps.length > 0 ? root.steps[root.step].title : ""
                color: Theme.text
                font.pixelSize: 17
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                text: root.steps.length > 0 ? root.steps[root.step].text : ""
                color: Theme.sub
                font.pixelSize: Theme.body
                lineHeight: 1.25
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 8
                spacing: 8
                Btn { text: "Skip"; kind: "ghost"; visible: root.step < root.steps.length - 1; onClicked: root.stop() }
                Item { Layout.fillWidth: true }
                Btn { text: "Back"; kind: "ghost"; visible: root.step > 0; onClicked: root.back() }
                Btn { text: root.step < root.steps.length - 1 ? "Next" : "Done"; kind: "primary"; onClicked: root.next() }
            }
        }
    }
}
