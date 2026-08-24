import QtQuick
import QtQuick.Layouts
import Quintara

ColumnLayout {
    id: root
    required property var error
    property bool compact: false
    signal retry()
    spacing: Theme.space2

    StatusBadge {
        Layout.alignment: Qt.AlignHCenter
        text: qsTr("操作未完成")
        tone: "error"
    }
    Text {
        Layout.fillWidth: true
        text: root.error && root.error.title ? root.error.title : qsTr("页面暂时不可用")
        color: Theme.textPrimary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.sectionSize
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
        visible: !root.compact
    }
    Text {
        Layout.fillWidth: true
        text: root.error && root.error.impact ? root.error.impact : ""
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.captionSize
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
    }
    Text {
        Layout.fillWidth: true
        text: root.error && root.error.message ? root.error.message : qsTr("请稍后重试。")
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
        visible: !root.compact
    }
    AppButton {
        Layout.alignment: Qt.AlignHCenter
        text: qsTr("重试")
        primary: true
        onClicked: root.retry()
    }
}
