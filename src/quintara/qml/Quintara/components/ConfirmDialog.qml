import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Quintara

Dialog {
    id: root
    property string heading: ""
    property string message: ""
    property string confirmText: qsTr("确认")
    signal acceptedAction()
    modal: true
    closePolicy: Popup.CloseOnEscape
    padding: Theme.space3
    background: Rectangle { color: Theme.surface; radius: Theme.radiusLarge; border.color: Theme.outline }
    contentItem: ColumnLayout {
        Accessible.name: root.heading
        spacing: Theme.space2
        Text { text: root.heading; color: Theme.textPrimary; font.pixelSize: Theme.sectionSize; font.weight: Font.DemiBold }
        Text { Layout.fillWidth: true; text: root.message; color: Theme.textMuted; wrapMode: Text.Wrap }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            AppButton { text: qsTr("取消"); onClicked: root.reject() }
            AppButton { primary: true; text: root.confirmText; onClicked: { root.acceptedAction(); root.accept() } }
        }
    }
}
