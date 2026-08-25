import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quintara

ApplicationWindow {
    id: window
    objectName: "mainWindow"
    required property var backend
    width: 1200
    height: 760
    minimumWidth: 960
    minimumHeight: 640
    visible: true
    title: qsTr("Quintara · 本地 A 股研究")
    color: Theme.canvas
    property bool confirmedClose: false

    AppShell {
        id: appShell
        anchors.fill: parent
        backend: window.backend
    }

    OnboardingDialog {
        id: onboardingDialog
        backend: window.backend
        onCsvRequested: appShell.openCsvDialog()
        onBaostockRequested: window.backend.prepareDataUpdate(true)
        onStorageRequested: appShell.openContentRootDialog()
    }

    Dialog {
        id: updatePlanDialog
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(680, window.width - Theme.space4 * 2)
        modal: true
        closePolicy: Popup.CloseOnEscape
        title: qsTr("确认 BaoStock 数据计划")
        standardButtons: Dialog.NoButton
        padding: Theme.space4
        background: Rectangle { color: Theme.surface; radius: Theme.radiusLarge; border.color: Theme.outline }
        contentItem: ColumnLayout {
            spacing: Theme.space2
            Text {
                Layout.fillWidth: true
                text: qsTr("发布前预览")
                color: Theme.primary
                font.pixelSize: Theme.captionSize
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: qsTr("从 %1 更新至 %2").arg(window.backend.dataUpdatePreview.current_cutoff || "尚无数据").arg(window.backend.dataUpdatePreview.target_cutoff || "—")
                color: Theme.textPrimary
                font.pixelSize: Theme.titleSize
                font.weight: Font.DemiBold
                wrapMode: Text.Wrap
            }
            Repeater {
                model: [
                    {"label": qsTr("股票池与数量"), "value": (window.backend.dataUpdatePreview.membership_route || "PIT_BASELINE") + " · " + (window.backend.dataUpdatePreview.stock_count || 0) + qsTr(" 只")},
                    {"label": qsTr("新增交易日"), "value": (window.backend.dataUpdatePreview.start_session || "—") + " · " + (window.backend.dataUpdatePreview.trading_sessions || 0) + qsTr(" 个交易日")},
                    {"label": qsTr("字段与复权"), "value": (window.backend.dataUpdatePreview.fields || "—") + " · " + (window.backend.dataUpdatePreview.adjustflag || "—")},
                    {"label": qsTr("原数据口径"), "value": (window.backend.dataUpdatePreview.current_adjustment || "未标记") + " · " + JSON.stringify(window.backend.dataUpdatePreview.current_units || {})},
                    {"label": qsTr("预计下载"), "value": Math.round((window.backend.dataUpdatePreview.estimated_download_bytes || 0) / 1024 / 1024 * 10) / 10 + " MiB"},
                    {"label": qsTr("磁盘预算"), "value": Math.round((window.backend.dataUpdatePreview.disk_required_bytes || 0) / 1024 / 1024) + " MiB / " + Math.round((window.backend.dataUpdatePreview.disk_free_bytes || 0) / 1024 / 1024) + " MiB " + (window.backend.dataUpdatePreview.disk_ok ? qsTr("可用") : qsTr("需更换工作目录"))},
                    {"label": qsTr("保存位置"), "value": window.backend.dataUpdatePreview.content_root || "—"},
                    {"label": qsTr("身份变化"), "value": window.backend.dataUpdatePreview.identity_change || "—"}
                ]
                delegate: Frame {
                    id: planRow
                    required property var modelData
                    Layout.fillWidth: true
                    padding: Theme.space2
                    background: Rectangle { color: Theme.surfaceRaised; radius: Theme.radiusSmall; border.color: Theme.outline }
                    contentItem: ColumnLayout {
                        Text { text: planRow.modelData.label; color: Theme.textMuted; font.pixelSize: Theme.captionSize }
                        TextEdit {
                            Layout.fillWidth: true
                            text: planRow.modelData.value
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.WrapAnywhere
                            color: Theme.textPrimary
                        }
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                text: qsTr("所有下载先写入暂存区。登录、查询、字段、单位、复权、PIT、OHLC、磁盘或取消检查有异常时，当前活动数据继续保持原版本。")
                color: Theme.textMuted
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton { text: qsTr("返回调整"); onClicked: updatePlanDialog.close() }
                AppButton {
                    primary: true
                    enabled: Boolean(window.backend.dataUpdatePreview.disk_ok)
                    text: qsTr("确认并开始")
                    onClicked: {
                        updatePlanDialog.close()
                        window.backend.confirmDataUpdate()
                    }
                }
            }
        }
    }

    ConfirmDialog {
        id: stopAndCloseDialog
        heading: qsTr("停止任务并退出？")
        message: qsTr("Quintara 会先请求在安全点停止；尚未发布的临时工件会清理，上一份结果保持可用。")
        confirmText: qsTr("停止并退出")
        onAcceptedAction: {
            window.backend.cancelTraining()
            window.confirmedClose = true
            window.close()
        }
    }

    onClosing: function(close) {
        if (window.backend.jobRunning && !window.confirmedClose) {
            close.accepted = false
            stopAndCloseDialog.open()
        }
    }

    Component.onCompleted: Theme.darkMode = window.backend.effectiveDark
    Connections {
        target: window.backend
        function onThemeChanged() { Theme.darkMode = window.backend.effectiveDark }
        function onUpdatePreviewChanged() {
            if (Object.keys(window.backend.dataUpdatePreview).length > 0)
                updatePlanDialog.open()
        }
    }
}
