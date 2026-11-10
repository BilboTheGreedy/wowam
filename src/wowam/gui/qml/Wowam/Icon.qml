import QtQuick
import QtQuick.Controls.impl
import Wowam

IconImage {
    property string shape: ""
    property int size: 18
    width: size
    height: size
    sourceSize.width: size
    sourceSize.height: size
    source: shape ? Qt.resolvedUrl("icons/" + shape + ".svg") : ""
    color: Theme.sub
}
