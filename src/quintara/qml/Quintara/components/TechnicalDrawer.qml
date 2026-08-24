import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Quintara

Drawer {
    id: root
    required property var details
    edge: Qt.RightEdge
    width: Math.min(520, parent ? parent.width * 0.86 : 520)
    height: parent ? parent.height : 640
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle { color: Theme.surface }
    contentItem: ColumnLayout {
        Accessible.name: qsTr("技术详情")
        spacing: Theme.space2
        Text {
            Layout.fillWidth: true
            text: root.details && root.details.title ? root.details.title : qsTr("技术详情")
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.sectionSize
            font.weight: Font.DemiBold
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            TextArea {
                text: root.details && root.details.copy_text ? root.details.copy_text : ""
                color: Theme.textPrimary
                font.family: "monospace"
                font.pixelSize: Theme.captionSize
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                background: Rectangle { color: Theme.surfaceRaised; radius: Theme.radiusSmall }
            }
        }
        AppButton {
            Layout.alignment: Qt.AlignRight
            text: qsTr("关闭")
            onClicked: root.close()
        }
    }
}
