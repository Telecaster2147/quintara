import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Quintara

Dialog {
    id: root
    required property var backend
    signal csvRequested()
    readonly property int step: backend ? backend.onboardingStep : 0
    property string source: (backend && backend.onboardingSource === "csv") ? "csv" : "provider"
    property bool acceptedLicense: false
    property bool acceptedTransfer: false
    property bool acceptedRisk: backend ? backend.consentConfirmed : false
    readonly property var sourceSummary: backend ? backend.onboardingDataSummary : ({})
    readonly property var titles: [
        qsTr("先确认研究边界"),
        qsTr("检查这台电脑"),
        qsTr("选择数据来源"),
        qsTr("确认本地存储"),
        qsTr("准备完成")
    ]
    readonly property var descriptions: [
        qsTr("Quintara 仅用于本地量化研究；结果不是收益保证或交易指令。"),
        qsTr("Quintara 会检查操作系统、CPU、内存、磁盘、GPU 和 Qt 图形平台，不修改系统设置。"),
        qsTr("标准生产数据与用户 CSV 二选一；以后可在数据页重新选择。"),
        qsTr("数据、模型和结果保存在你选择的本机目录，可在设置中迁移。"),
        qsTr("先准备研究数据，Quintara 会引导你完成股票池、训练和 Top-5 结果。")
    ]

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(620, parent ? parent.width - Theme.space4 * 2 : 620)
    modal: true
    visible: Boolean(backend && backend.onboardingRequired)
    closePolicy: Popup.NoAutoClose
    padding: Theme.space4

    onStepChanged: {
        if (root.step === 2 && root.backend && root.backend.onboardingSource) {
            root.source = root.backend.onboardingSource
        }
    }
    onVisibleChanged: if (visible && root.backend && root.backend.consentConfirmed) root.acceptedRisk = true

    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusLarge
        border.color: Theme.outline
    }
    contentItem: ColumnLayout {
        Accessible.name: qsTr("首次使用向导")
        spacing: Theme.space3
        Text {
            text: qsTr("第 %1 步，共 5 步").arg(root.step + 1)
            color: Theme.primary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
        }
        Text {
            Layout.fillWidth: true
            text: root.titles[root.step]
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.titleSize
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
        }
        AppButton {
            visible: root.step === 0
            text: (root.acceptedRisk ? "✓ " : "□ ") + qsTr("我已阅读并理解这项研究用途声明")
            onClicked: root.acceptedRisk = !root.acceptedRisk
        }
        Text {
            Layout.fillWidth: true
            text: root.descriptions[root.step]
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            lineHeight: 1.45
            wrapMode: Text.Wrap
        }

        GridLayout {
            visible: root.step === 1
            Layout.fillWidth: true
            columns: root.width >= 520 ? 2 : 1
            columnSpacing: Theme.space2
            rowSpacing: Theme.space2
            Repeater {
                model: [
                    {"title": qsTr("CPU 路径"), "value": qsTr("可用，权威训练路径")},
                    {"title": qsTr("内存与磁盘"), "value": qsTr("启动后显示实时容量")},
                    {"title": qsTr("GPU"), "value": qsTr("实验加速，可选")},
                    {"title": qsTr("图形平台"), "value": qsTr("自动选择 Wayland / XCB / Windows")}
                ]
                delegate: Frame {
                    id: envCard
                    required property var modelData
                    Layout.fillWidth: true
                    padding: Theme.space2
                    background: Rectangle {
                        color: Theme.surfaceRaised
                        radius: Theme.radiusSmall
                        border.color: Theme.outline
                    }
                    contentItem: ColumnLayout {
                        Text { text: envCard.modelData.title; color: Theme.textMuted; font.pixelSize: Theme.captionSize }
                        Text { text: envCard.modelData.value; color: Theme.textPrimary; font.pixelSize: Theme.bodySize; wrapMode: Text.Wrap }
                    }
                }
            }
        }

        RowLayout {
            visible: root.step === 2
            Layout.fillWidth: true
            AppButton {
                Layout.fillWidth: true
                primary: root.source === "provider"
                text: qsTr("Quintara 标准数据")
                onClicked: root.source = "provider"
            }
            AppButton {
                Layout.fillWidth: true
                primary: root.source === "csv"
                text: qsTr("我自己的 CSV")
                onClicked: root.source = "csv"
            }
        }
        ColumnLayout {
            visible: root.step === 2 && root.source === "provider"
            Layout.fillWidth: true
            spacing: Theme.space1
            Text {
                Layout.fillWidth: true
                text: qsTr("标准数据来源摘要")
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.sectionSize
                font.weight: Font.DemiBold
            }
            Text { text: qsTr("版本：%1").arg(root.sourceSummary.version || "—"); color: Theme.textMuted; wrapMode: Text.Wrap }
            Text { text: qsTr("覆盖：%1").arg(root.sourceSummary.coverage || "—"); color: Theme.textMuted; wrapMode: Text.Wrap }
            Text { text: qsTr("预计体积：%1").arg(root.sourceSummary.size || "—"); color: Theme.textMuted; wrapMode: Text.Wrap }
            Text { text: qsTr("本地位置：%1").arg(root.sourceSummary.location || "—"); color: Theme.textMuted; elide: Text.ElideMiddle }
            AppButton {
                text: (root.acceptedLicense ? "✓ " : "□ ") + qsTr("已阅读数据许可")
                onClicked: root.acceptedLicense = !root.acceptedLicense
            }
            AppButton {
                text: (root.acceptedTransfer ? "✓ " : "□ ") + qsTr("确认开始联网传输前再次显示大小和来源")
                onClicked: root.acceptedTransfer = !root.acceptedTransfer
            }
        }
        ColumnLayout {
            visible: root.step === 2 && root.source === "csv"
            Layout.fillWidth: true
            spacing: Theme.space1
            Text {
                Layout.fillWidth: true
                text: qsTr("CSV 会先只读检查；原文件保持原样，检查通过后再复制到本机数据仓库。")
                color: Theme.textMuted
                wrapMode: Text.Wrap
            }
            AppButton {
                primary: true
                enabled: root.acceptedRisk
                text: qsTr("选择并检查 CSV")
                onClicked: root.csvRequested()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            AppButton {
                visible: root.step > 0 && root.step < 4
                text: qsTr("稍后完成")
                onClicked: root.backend.skipOnboarding()
            }
            Item { Layout.fillWidth: true }
            AppButton {
                primary: true
                text: root.step === 4 ? qsTr("进入工作台") : qsTr("继续")
                enabled: (root.step !== 0 || root.acceptedRisk) && (root.step !== 2 || root.source === "csv" || (root.acceptedLicense && root.acceptedTransfer))
                onClicked: root.backend.advanceOnboarding(
                    Math.min(root.step + 1, 4),
                    root.step === 2 ? root.source : "",
                    root.acceptedRisk,
                    root.acceptedLicense,
                    root.acceptedTransfer
                )
            }
        }
    }
}
