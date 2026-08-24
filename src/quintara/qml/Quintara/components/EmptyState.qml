import QtQuick
import QtQuick.Layouts
import Quintara

ColumnLayout {
    id: root
    required property string title
    required property string message
    property string actionText: ""
    signal activated()
    spacing: Theme.space2

    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: 72
        Layout.preferredHeight: 72
        radius: 36
        color: Qt.alpha(Theme.primary, 0.13)
        Text {
            anchors.centerIn: parent
            text: "◎"
            color: Theme.primary
            font.pixelSize: 36
            Accessible.ignored: true
        }
    }
    Text {
        Layout.fillWidth: true
        text: root.title
        color: Theme.textPrimary
        horizontalAlignment: Text.AlignHCenter
        font.family: Theme.fontFamily
        font.pixelSize: Theme.sectionSize
        font.weight: Font.DemiBold
        wrapMode: Text.Wrap
    }
    Text {
        Layout.fillWidth: true
        text: root.message
        color: Theme.textMuted
        horizontalAlignment: Text.AlignHCenter
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
        wrapMode: Text.Wrap
    }
    AppButton {
        Layout.alignment: Qt.AlignHCenter
        visible: root.actionText.length > 0
        primary: true
        text: root.actionText
        onClicked: root.activated()
    }
}
