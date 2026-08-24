import QtQuick
import Quintara

Rectangle {
    id: root
    required property string text
    property string tone: "neutral"

    implicitWidth: label.implicitWidth + Theme.space2
    implicitHeight: 28
    radius: 14
    color: root.tone === "success" ? Qt.alpha(Theme.success, 0.16)
         : root.tone === "warning" ? Qt.alpha(Theme.warning, 0.16)
         : root.tone === "error" ? Qt.alpha(Theme.error, 0.16)
         : Qt.alpha(Theme.primary, 0.13)
    Accessible.role: Accessible.StaticText
    Accessible.name: root.text

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.tone === "success" ? Theme.success
             : root.tone === "warning" ? Theme.warning
             : root.tone === "error" ? Theme.error
             : Theme.primary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.captionSize
        font.weight: Font.DemiBold
    }
}
