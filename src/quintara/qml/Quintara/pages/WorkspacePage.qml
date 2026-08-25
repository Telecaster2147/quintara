pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Quintara
import "../components"

ScrollView {
    id: root
    required property var page
    signal navigate(string target)
    signal primaryAction(string key, string target)
    signal secondaryAction(string key, string target)
    signal cancelJob()
    signal themeRequested(string value)
    signal reducedMotionRequested(bool value)
    property bool reducedMotion: false
    property bool jobRunning: false
    property string themeMode: "system"

    contentWidth: availableWidth
    background: Item {}

    function resetContentPosition() {
        if (root.contentItem) root.contentItem.contentY = 0
    }
    onPageChanged: Qt.callLater(resetContentPosition)
    Component.onCompleted: Qt.callLater(resetContentPosition)

    ColumnLayout {
        width: root.availableWidth
        spacing: Theme.space3

        Text {
            Layout.fillWidth: true
            text: root.page && root.page.eyebrow ? root.page.eyebrow : ""
            color: Theme.primary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 1.1
        }
        Text {
            Layout.fillWidth: true
            text: root.page && root.page.title ? root.page.title : qsTr("Quintara")
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.titleSize
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            Layout.maximumWidth: 760
            text: root.page && root.page.summary ? root.page.summary : ""
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            lineHeight: 1.5
            wrapMode: Text.Wrap
        }
        ErrorState {
            Layout.fillWidth: true
            Layout.topMargin: Theme.space3
            visible: Boolean(root.page && root.page.status === "error")
            compact: true
            error: root.page ? root.page.error : null
            onRetry: root.primaryAction("retry", "")
        }
        AppButton {
            visible: Boolean(root.page && root.page.status !== "error" && root.page.primary_action)
            primary: true
            text: visible ? root.page.primary_action.label : ""
            onClicked: root.primaryAction(root.page.primary_action.key, root.page.primary_action.target)
        }
        RowLayout {
            visible: Boolean(root.page && root.page.actions && root.page.actions.length > 0)
            Repeater {
                model: root.page && root.page.actions ? root.page.actions : []
                delegate: AppButton {
                    required property var modelData
                    text: modelData.label || ""
                    onClicked: root.secondaryAction(modelData.key || "", modelData.target || "")
                }
            }
        }
        ColumnLayout {
            visible: Boolean(root.page && root.page.key === "settings")
            spacing: Theme.space2
            Text { text: qsTr("显示主题"); color: Theme.textPrimary; font.pixelSize: Theme.sectionSize; font.weight: Font.DemiBold }
            RowLayout {
                AppButton { text: qsTr("跟随系统"); primary: root.themeMode === "system"; onClicked: root.themeRequested("system") }
                AppButton { text: qsTr("浅色"); primary: root.themeMode === "light"; onClicked: root.themeRequested("light") }
                AppButton { text: qsTr("深色"); primary: root.themeMode === "dark"; onClicked: root.themeRequested("dark") }
            }
            AppButton {
                text: (root.reducedMotion ? "✓ " : "□ ") + qsTr("减少动态效果")
                onClicked: root.reducedMotionRequested(!root.reducedMotion)
            }
        }
        SkeletonBlock {
            Layout.fillWidth: true
            visible: Boolean(root.page && root.page.status === "loading")
            reducedMotion: root.reducedMotion
        }
        AppButton {
            visible: root.jobRunning
            text: qsTr("停止任务")
            onClicked: root.cancelJob()
        }

        GridLayout {
            Layout.fillWidth: true
            columns: root.availableWidth >= 900 ? 2 : 1
            columnSpacing: Theme.space2
            rowSpacing: Theme.space2
            Repeater {
                model: root.page && root.page.cards ? root.page.cards : []
                delegate: StatusCard {
                    required property var modelData
                    Layout.fillWidth: true
                    title: modelData.title || ""
                    summary: modelData.summary || modelData.value || ""
                    status: modelData.status || (modelData.tone === "warning" ? "empty" : "ready")
                    target: modelData.target || ""
                    onActivated: target => root.navigate(target)
                }
            }
        }

        DataTable {
            Layout.fillWidth: true
            visible: Boolean(root.page && root.page.rows && root.page.rows.length > 0)
            rows: root.page && root.page.rows ? root.page.rows : []
            searchable: Boolean(root.page && (root.page.key === "universe" || root.page.key === "history"))
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: Boolean(root.page && root.page.path_rows && root.page.path_rows.length > 0)
            spacing: Theme.space1

            Text {
                text: qsTr("当前路径")
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.sectionSize
                font.weight: Font.DemiBold
            }
            Repeater {
                model: root.page && root.page.path_rows ? root.page.path_rows : []
                delegate: Frame {
                    id: pathDelegate
                    required property var modelData
                    Layout.fillWidth: true
                    padding: Theme.space2
                    background: Rectangle {
                        color: Theme.surfaceRaised
                        radius: Theme.radiusSmall
                        border.color: Theme.outline
                    }
                    contentItem: ColumnLayout {
                        spacing: 4
                        Text {
                            text: pathDelegate.modelData.label || qsTr("路径")
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                        }
                        TextEdit {
                            Layout.fillWidth: true
                            text: pathDelegate.modelData.path || ""
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.WrapAnywhere
                            color: Theme.textPrimary
                            selectionColor: Theme.primary
                            selectedTextColor: Theme.textOnPrimary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            Accessible.name: qsTr("%1：%2").arg(pathDelegate.modelData.label || qsTr("路径")).arg(text)
                        }
                    }
                }
            }
        }

        EmptyState {
            Layout.fillWidth: true
            Layout.topMargin: Theme.space4
            visible: Boolean(root.page && root.page.status === "empty" && (!root.page.cards || root.page.cards.length === 0))
            title: root.page && root.page.title ? root.page.title : qsTr("等待开始")
            message: root.page && root.page.summary ? root.page.summary : ""
            actionText: root.page && root.page.primary_action ? root.page.primary_action.label : ""
            onActivated: root.primaryAction(root.page.primary_action.key, root.page.primary_action.target)
        }

        Repeater {
            model: root.page && root.page.notices ? root.page.notices : []
            delegate: Frame {
                id: noticeDelegate
                required property var modelData
                Layout.fillWidth: true
                padding: Theme.space2
                background: Rectangle {
                    color: noticeDelegate.modelData.tone === "warning" ? Qt.alpha(Theme.warning, 0.12) : Qt.alpha(Theme.primary, 0.10)
                    radius: Theme.radiusSmall
                    border.color: noticeDelegate.modelData.tone === "warning" ? Qt.alpha(Theme.warning, 0.5) : Qt.alpha(Theme.primary, 0.35)
                }
                contentItem: Text {
                    text: noticeDelegate.modelData.text || ""
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    wrapMode: Text.Wrap
                }
            }
        }

        AppButton {
            visible: Boolean(root.page && root.page.technical)
            text: qsTr("查看技术详情")
            onClicked: detailsLoader.active = true
        }
    }

    Loader {
        id: detailsLoader
        active: false
        asynchronous: true
        sourceComponent: Component {
            TechnicalDrawer {
                details: root.page ? root.page.technical : null
                Component.onCompleted: open()
                onClosed: detailsLoader.active = false
            }
        }
    }
}
