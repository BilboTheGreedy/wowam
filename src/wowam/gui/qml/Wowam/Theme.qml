pragma Singleton
import QtQuick

QtObject {
    property string mode: ""
    readonly property bool dark: mode === "dark" || (mode !== "light" && Qt.styleHints.colorScheme !== Qt.ColorScheme.Light)
    property SystemPalette sys: SystemPalette { colorGroup: SystemPalette.Active }

    readonly property color accent: mode === "" ? sys.highlight : "#5b8cff"
    readonly property color onAccent: luminance(accent) > 0.18 ? "#10131a" : "#ffffff"
    readonly property color accentSoft: Qt.rgba(accent.r, accent.g, accent.b, dark ? 0.16 : 0.12)
    readonly property color accentText: dark ? Qt.lighter(accent, 1.35) : Qt.darker(accent, 1.25)

    readonly property color bg: dark ? "#0e1014" : "#f4f5f8"
    readonly property color panel: dark ? "#13161c" : "#ebedf2"
    readonly property color card: dark ? "#181c24" : "#ffffff"
    readonly property color cardHover: dark ? "#1e232d" : "#f6f7fa"
    readonly property color raised: dark ? "#222835" : "#ffffff"
    readonly property color line: dark ? "#262c38" : "#dde1e9"
    readonly property color text: dark ? "#eceef3" : "#171a21"
    readonly property color sub: dark ? "#939bae" : "#5d6779"
    readonly property color faint: dark ? "#626b7e" : "#98a1b3"

    readonly property color ok: dark ? "#3fcf8e" : "#15925a"
    readonly property color warn: dark ? "#f2a93b" : "#b4720b"
    readonly property color err: dark ? "#f0616d" : "#c93545"

    readonly property int radius: 10
    readonly property int small: 12
    readonly property int body: 13
    readonly property int title: 22

    function tint(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    function linear(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    function luminance(c) { return 0.2126 * linear(c.r) + 0.7152 * linear(c.g) + 0.0722 * linear(c.b) }

    function statusColor(status) {
        if (status === "ok") return ok
        if (status === "update" || status === "suggest") return accentText
        if (status === "error") return err
        if (status === "modified" || status === "pinned") return warn
        return sub
    }

    readonly property var avatarHues: [0.58, 0.72, 0.86, 0.02, 0.09, 0.38, 0.47, 0.64]
    function avatar(name) {
        var h = 0
        for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 9973
        return Qt.hsla(avatarHues[h % avatarHues.length], dark ? 0.55 : 0.6, dark ? 0.58 : 0.5, 1)
    }
}
