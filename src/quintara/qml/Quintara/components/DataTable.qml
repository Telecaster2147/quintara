pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Quintara

Frame {
    id: root
    required property var rows
    property bool searchable: false
    property string query: ""
    padding: Theme.space2
    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusMedium
        border.color: Theme.outline
    }
    contentItem: ColumnLayout {
        spacing: 0
        TextField {
            Layout.fillWidth: true
            visible: root.searchable
            placeholderText: qsTr("搜索名称、代码或状态")
            activeFocusOnTab: true
            Accessible.name: qsTr("搜索表格")
            onTextChanged: root.query = text.trim().toLowerCase()
            color: Theme.textPrimary
            background: Rectangle { color: Theme.surfaceRaised; radius: Theme.radiusSmall; border.color: Theme.outline }
        }
        Repeater {
            model: (root.rows || []).filter(function(row) {
                return !root.query || JSON.stringify(row).toLowerCase().indexOf(root.query) >= 0
            })
            delegate: RowLayout {
                id: rowDelegate
                required property var modelData
                Layout.fillWidth: true
                Layout.minimumHeight: rowDelegate.modelData.code ? 64 : Theme.clickTarget
                spacing: Theme.space2
                Accessible.name: [modelData.name || modelData.title || modelData.code || modelData.id || "", modelData.status || modelData.state || modelData.mode || ""].join(" ")
                Text {
                    Layout.preferredWidth: rowDelegate.modelData.rank ? 36 : 0
                    visible: Boolean(rowDelegate.modelData.rank)
                    text: rowDelegate.modelData.rank || ""
                    color: Theme.primary
                    font.family: Theme.fontFamily
                    font.weight: Font.DemiBold
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        text: rowDelegate.modelData.name || rowDelegate.modelData.title || rowDelegate.modelData.code || rowDelegate.modelData.id || ""
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize
                        elide: Text.ElideRight
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: Boolean(rowDelegate.modelData.code || rowDelegate.modelData.explanation)
                        text: [rowDelegate.modelData.code || "", rowDelegate.modelData.exchange || "", rowDelegate.modelData.explanation || ""].filter(Boolean).join(" · ")
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        elide: Text.ElideRight
                    }
                }
                Text {
                    text: rowDelegate.modelData.weight !== undefined ? Number(rowDelegate.modelData.weight * 100).toFixed(0) + "%"
                          : rowDelegate.modelData.text || rowDelegate.modelData.value || rowDelegate.modelData.status || rowDelegate.modelData.state || rowDelegate.modelData.mode || ""
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                }
            }
        }
    }
}
