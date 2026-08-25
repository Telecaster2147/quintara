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
    property real jobProgress: 0.0
    property string jobStage: ""
    property int jobElapsedSeconds: 0
    property var jobLogs: []
    property string themeMode: "system"

    contentWidth: availableWidth
    contentHeight: contentColumn.implicitHeight
    clip: true
    background: Item {}
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ScrollBar.vertical: ScrollBar {
        id: verticalBar
        objectName: "workspaceVerticalScrollBar"
        parent: root
        x: root.width - width
        y: 0
        height: root.height
        policy: ScrollBar.AlwaysOn
        visible: root.contentHeight > root.availableHeight + 1
        interactive: true
        width: 8
        contentItem: Rectangle {
            implicitWidth: 8
            radius: 4
            color: Theme.primary
            opacity: verticalBar.visible ? (verticalBar.pressed ? 0.85 : 0.55) : 0
        }
        background: Item {}
    }

    function resetContentPosition() {
        if (root.contentItem) root.contentItem.contentY = 0
    }
    onPageChanged: Qt.callLater(resetContentPosition)
    Component.onCompleted: Qt.callLater(resetContentPosition)

    ColumnLayout {
        id: contentColumn
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
            text: root.page && root.page.key === "data" ? qsTr("停止数据更新") : qsTr("停止任务")
            Accessible.name: text
            onClicked: root.cancelJob()
        }

        Frame {
            id: jobProgressPanel
            objectName: "jobProgressPanel"
            Layout.fillWidth: true
            visible: Boolean(root.page && (root.page.key === "train" || root.page.key === "data") && root.jobLogs.length > 0)
            padding: Theme.space3
            background: Rectangle {
                color: Theme.surface
                radius: Theme.radiusMedium
                border.color: Theme.outline
            }
            contentItem: ColumnLayout {
                spacing: Theme.space2
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: root.page && root.page.key === "data" ? qsTr("数据更新实时进度") : qsTr("训练实时进度")
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.sectionSize
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: qsTr("已用时 %1").arg(root.jobElapsedSeconds < 60
                            ? qsTr("%1 秒").arg(root.jobElapsedSeconds)
                            : qsTr("%1 分 %2 秒").arg(Math.floor(root.jobElapsedSeconds / 60)).arg(root.jobElapsedSeconds % 60))
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                    }
                }
                ProgressBar {
                    objectName: "jobProgressBar"
                    Layout.fillWidth: true
                    from: 0
                    to: 1
                    value: root.jobProgress
                    indeterminate: root.jobRunning && root.jobProgress <= 0
                    Accessible.name: (root.page && root.page.key === "data" ? qsTr("数据更新进度 %1%") : qsTr("训练进度 %1%")).arg(Math.round(root.jobProgress * 100))
                }
                Repeater {
                    model: root.jobLogs
                    delegate: RowLayout {
                        id: logRow
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Theme.space2
                        StatusBadge {
                            text: logRow.modelData.severity === "error" ? qsTr("失败")
                                : logRow.modelData.severity === "warning" ? qsTr("提醒")
                                : logRow.modelData.severity === "success" ? qsTr("完成") : qsTr("进行中")
                            tone: logRow.modelData.severity === "error" ? "error"
                                : logRow.modelData.severity === "warning" ? "warning"
                                : logRow.modelData.severity === "success" ? "success" : "info"
                        }
                        Text {
                            Layout.fillWidth: true
                            text: logRow.modelData.message || ""
                            color: Theme.textPrimary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            wrapMode: Text.Wrap
                        }
                        Text {
                            text: qsTr("%1 秒").arg(logRow.modelData.elapsed_seconds || 0)
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                        }
                    }
                }
            }
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
