import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Quintara

Frame {
    id: root
    required property string title
    required property string summary
    property string status: "ready"
    property string target: ""
    signal activated(string target)

    padding: Theme.space3
    Accessible.name: qsTr("%1：%2").arg(title).arg(summary)
    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusMedium
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? Theme.focus : Theme.outline
    }

    contentItem: ColumnLayout {
        spacing: Theme.space2
        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: root.title
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.sectionSize
                font.weight: Font.DemiBold
            }
            StatusBadge {
                text: root.status === "ready" ? qsTr("已就绪")
                    : root.status === "empty" ? qsTr("待完成") : qsTr("需处理")
                tone: root.status === "ready" ? "success"
                    : root.status === "empty" ? "warning" : "error"
            }
        }
        Text {
            Layout.fillWidth: true
            text: root.summary
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            lineHeight: 1.45
            wrapMode: Text.Wrap
        }
        AppButton {
            visible: root.target.length > 0
            text: qsTr("查看详情")
            onClicked: root.activated(root.target)
        }
    }
}
