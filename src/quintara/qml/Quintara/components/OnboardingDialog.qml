import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Quintara

Dialog {
    id: root
    required property var backend
    signal csvRequested()
    signal baostockRequested()
    signal storageRequested()
    readonly property int step: backend ? backend.onboardingStep : 0
    property string source: (backend && ["bundled", "baostock", "csv"].indexOf(backend.onboardingSource) >= 0)
                            ? backend.onboardingSource : "bundled"
    property bool acceptedRisk: backend ? backend.consentConfirmed : false
    property bool acceptedLicense: false
    property bool acceptedTransfer: false
    readonly property var sourceSummary: backend ? backend.onboardingDataSummary : ({})
    readonly property var paths: backend ? backend.pathSummary : ({})
    readonly property var titles: [
        qsTr("先读清楚研究边界"),
        qsTr("了解软件会做什么"),
        qsTr("选择并准备数据"),
        qsTr("确认每个文件位置"),
        qsTr("逐项检查后开始")
    ]
    readonly property var descriptions: [
        qsTr("下面五项分别说明用途、数据、模型、决策责任和本地隐私。请逐项阅读，再在本页底部确认。"),
        qsTr("Quintara 按“读取已校验数据 → 建立历史股票池 → 训练排序模型 → 生成五只股票及固定权重 → 保存可复查记录”的顺序工作。"),
        qsTr("可选择安装包自带数据、BaoStock 在线初始化或自己的 CSV。三种来源相互独立，都会先预览计划并经过完整性检查。"),
        qsTr("自带数据包留在应用安装目录；活动数据、模型和结果写入当前工作目录。修改路径后，本页和设置页持续显示最新位置。"),
        qsTr("完成设置后先训练一次。开发者数据的输出会与包内参考结果逐行及哈希核对，通过后才发布到结果页。")
    ]

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(760, parent ? parent.width - Theme.space4 * 2 : 760)
    height: Math.min(700, parent ? parent.height - Theme.space3 * 2 : 700)
    modal: true
    visible: Boolean(backend && backend.onboardingRequired)
    closePolicy: Popup.NoAutoClose
    padding: Theme.space4

    onStepChanged: {
        if (root.step === 2 && root.backend && root.backend.onboardingSource) {
            root.source = ["bundled", "baostock", "csv"].indexOf(root.backend.onboardingSource) >= 0
                          ? root.backend.onboardingSource : "bundled"
        }
    }
    onVisibleChanged: if (visible && root.backend && root.backend.consentConfirmed) root.acceptedRisk = true

    background: Rectangle {
        color: Theme.surface
        radius: Theme.radiusLarge
        border.color: Theme.outline
    }

    contentItem: ColumnLayout {
        Accessible.name: qsTr("首次使用向导，第 %1 步，共 5 步").arg(root.step + 1)
        spacing: Theme.space2

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("首次使用 · 第 %1/5 步").arg(root.step + 1)
                color: Theme.primary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                font.weight: Font.DemiBold
            }
            Item { Layout.fillWidth: true }
            Text {
                text: root.step === 4 ? qsTr("准备完成") : qsTr("还剩 %1 步").arg(4 - root.step)
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
            }
        }

        ProgressBar {
            Layout.fillWidth: true
            from: 0
            to: 5
            value: root.step + 1
            Accessible.name: qsTr("向导进度 %1/5").arg(root.step + 1)
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
        Text {
            Layout.fillWidth: true
            text: root.descriptions[root.step]
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            lineHeight: 1.45
            wrapMode: Text.Wrap
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            background: Item {}

            ColumnLayout {
                width: parent.width
                spacing: Theme.space2

                Repeater {
                    model: root.step === 0 && root.backend ? root.backend.onboardingDisclosures : []
                    delegate: Frame {
                        id: disclosureDelegate
                        required property var modelData
                        Layout.fillWidth: true
                        padding: Theme.space2
                        background: Rectangle {
                            color: Theme.surfaceRaised
                            radius: Theme.radiusSmall
                            border.color: Theme.outline
                        }
                        contentItem: ColumnLayout {
                            spacing: Theme.space1
                            Text {
                                text: disclosureDelegate.modelData.title || ""
                                color: Theme.textPrimary
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.sectionSize
                                font.weight: Font.DemiBold
                            }
                            Text {
                                Layout.fillWidth: true
                                text: disclosureDelegate.modelData.text || ""
                                color: Theme.textMuted
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.bodySize
                                lineHeight: 1.5
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }

                ColumnLayout {
                    visible: root.step === 1
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    Repeater {
                        model: [
                            {"title": qsTr("1. 完整性检查"), "text": qsTr("先核对数据清单、文件大小、SHA-256、股票代码、日期和关键数值。")},
                            {"title": qsTr("2. 本机训练"), "text": qsTr("CPU 默认执行固定参数训练；进度、失败阶段和运行编号写入本机。")},
                            {"title": qsTr("3. 结果核对"), "text": qsTr("开发者数据同时核对五只股票、顺序、权重和 CSV 哈希。")},
                            {"title": qsTr("4. 用户决定"), "text": qsTr("结果页提供来源、截止日期、模型身份和风险说明，由用户复查。")}
                        ]
                        delegate: Frame {
                            id: workflowDelegate
                            required property var modelData
                            Layout.fillWidth: true
                            padding: Theme.space2
                            background: Rectangle { color: Theme.surfaceRaised; radius: Theme.radiusSmall; border.color: Theme.outline }
                            contentItem: ColumnLayout {
                                Text { text: workflowDelegate.modelData.title; color: Theme.textPrimary; font.pixelSize: Theme.sectionSize; font.weight: Font.DemiBold }
                                Text { Layout.fillWidth: true; text: workflowDelegate.modelData.text; color: Theme.textMuted; font.pixelSize: Theme.bodySize; wrapMode: Text.Wrap }
                            }
                        }
                    }
                }

                ColumnLayout {
                    visible: root.step === 2
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    RowLayout {
                        Layout.fillWidth: true
                        AppButton {
                            Layout.fillWidth: true
                            primary: root.source === "bundled"
                            text: qsTr("安装包自带数据")
                            onClicked: root.source = "bundled"
                        }
                        AppButton {
                            Layout.fillWidth: true
                            primary: root.source === "baostock"
                            text: qsTr("BaoStock 在线初始化")
                            onClicked: root.source = "baostock"
                        }
                        AppButton {
                            Layout.fillWidth: true
                            primary: root.source === "csv"
                            text: qsTr("我自己的 CSV")
                            onClicked: root.source = "csv"
                        }
                    }
                    Frame {
                        visible: root.source === "baostock"
                        Layout.fillWidth: true
                        padding: Theme.space2
                        background: Rectangle { color: Theme.surfaceRaised; radius: Theme.radiusSmall; border.color: Theme.outline }
                        contentItem: ColumnLayout {
                            spacing: Theme.space1
                            Text {
                                Layout.fillWidth: true
                                text: qsTr("先连接 BaoStock 获取实际可用的最新完整交易日、历史沪深300成分、证券资料、日线行情和估值字段。确认目标日期、股票数、预计下载量、后复权口径和保存位置后再开始。")
                                color: Theme.textMuted
                                wrapMode: Text.Wrap
                            }
                            TextEdit {
                                Layout.fillWidth: true
                                text: qsTr("保存位置：%1").arg(root.paths.content_root || "—")
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.WrapAnywhere
                                color: Theme.textMuted
                            }
                            AppButton {
                                primary: true
                                enabled: Boolean(root.backend) && !root.backend.jobRunning
                                text: qsTr("读取 BaoStock 初始化计划")
                                onClicked: root.baostockRequested()
                            }
                        }
                    }
                    Frame {
                        visible: root.source === "bundled"
                        Layout.fillWidth: true
                        padding: Theme.space2
                        background: Rectangle { color: Theme.surfaceRaised; radius: Theme.radiusSmall; border.color: Theme.outline }
                        contentItem: ColumnLayout {
                            spacing: Theme.space1
                            Text { text: qsTr("版本：%1").arg(root.sourceSummary.version || "—"); color: Theme.textPrimary; wrapMode: Text.Wrap }
                            Text { text: qsTr("覆盖：%1").arg(root.sourceSummary.coverage || "—"); color: Theme.textMuted; wrapMode: Text.Wrap }
                            Text { text: qsTr("包体积：%1").arg(root.sourceSummary.size || "—"); color: Theme.textMuted; wrapMode: Text.Wrap }
                            TextEdit {
                                Layout.fillWidth: true
                                text: qsTr("安装位置：%1").arg(root.sourceSummary.location || "—")
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.WrapAnywhere
                                color: Theme.textMuted
                                font.pixelSize: Theme.bodySize
                            }
                            AppButton {
                                text: (root.acceptedLicense ? "✓ " : "□ ") + qsTr("我已理解此数据版本固定并用于本地研究复现")
                                onClicked: root.acceptedLicense = !root.acceptedLicense
                            }
                            AppButton {
                                primary: true
                                enabled: Boolean(root.backend) && root.acceptedLicense
                                         && root.backend.bundledDataAvailable && !root.backend.jobRunning
                                text: root.backend && root.backend.bundledDataImported
                                      ? qsTr("✓ 自带数据已校验并导入") : qsTr("校验并导入自带数据")
                                onClicked: if (root.backend) root.backend.importBundledData()
                            }
                        }
                    }
                    Frame {
                        visible: root.source === "csv"
                        Layout.fillWidth: true
                        padding: Theme.space2
                        background: Rectangle { color: Theme.surfaceRaised; radius: Theme.radiusSmall; border.color: Theme.outline }
                        contentItem: ColumnLayout {
                            Text {
                                Layout.fillWidth: true
                                text: qsTr("CSV 会先只读检查编码、字段、单位、代码、日期、重复键、OHLC 关系和历史长度。源文件保持原样。")
                                color: Theme.textMuted
                                wrapMode: Text.Wrap
                            }
                            AppButton { primary: true; text: qsTr("选择并检查 CSV"); onClicked: root.csvRequested() }
                        }
                    }
                }

                ColumnLayout {
                    visible: root.step === 3
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    Repeater {
                        model: [
                            {"label": qsTr("安装包自带数据"), "path": root.paths.bundled_data || "—"},
                            {"label": qsTr("当前工作目录"), "path": root.paths.content_root || "—"},
                            {"label": qsTr("当前活动数据"), "path": root.paths.active_data || "—"}
                        ]
                        delegate: Frame {
                            id: onboardingPathDelegate
                            required property var modelData
                            Layout.fillWidth: true
                            padding: Theme.space2
                            background: Rectangle { color: Theme.surfaceRaised; radius: Theme.radiusSmall; border.color: Theme.outline }
                            contentItem: ColumnLayout {
                                Text { text: onboardingPathDelegate.modelData.label; color: Theme.textMuted; font.pixelSize: Theme.captionSize }
                                TextEdit {
                                    Layout.fillWidth: true
                                    text: onboardingPathDelegate.modelData.path
                                    readOnly: true
                                    selectByMouse: true
                                    wrapMode: TextEdit.WrapAnywhere
                                    color: Theme.textPrimary
                                    font.pixelSize: Theme.bodySize
                                }
                            }
                        }
                    }
                    AppButton { text: qsTr("选择新的工作目录"); onClicked: root.storageRequested() }
                }

                ColumnLayout {
                    visible: root.step === 4
                    Layout.fillWidth: true
                    spacing: Theme.space2
                    Repeater {
                        model: [
                            {"ok": root.backend && root.backend.consentConfirmed, "text": qsTr("研究边界声明已确认")},
                            {"ok": root.backend && root.backend.activeDataAvailable, "text": qsTr("活动数据已校验")},
                            {"ok": Boolean(root.paths.content_root), "text": qsTr("当前工作目录已显示")},
                            {"ok": root.source !== "bundled" || (root.backend && root.backend.bundledDataImported), "text": qsTr("所选数据来源已绑定")}
                        ]
                        delegate: Text {
                            required property var modelData
                            Layout.fillWidth: true
                            text: (modelData.ok ? "✓ " : "○ ") + modelData.text
                            color: modelData.ok ? Theme.success : Theme.warning
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }

        AppButton {
            visible: root.step === 0
            Layout.fillWidth: true
            text: (root.acceptedRisk ? "✓ " : "□ ") + qsTr("我已逐项阅读并理解上述研究边界")
            onClicked: root.acceptedRisk = !root.acceptedRisk
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: root.backend && root.backend.jobRunning ? qsTr("正在处理数据，请保持窗口开启…") : ""
                color: Theme.primary
                font.pixelSize: Theme.captionSize
                wrapMode: Text.Wrap
            }
            AppButton {
                primary: true
                text: root.step === 4 ? qsTr("进入工作台") : qsTr("继续下一步")
                enabled: Boolean(root.backend) && !root.backend.jobRunning
                         && (root.step !== 0 || root.acceptedRisk)
                         && (root.step !== 2 || (root.backend.activeDataAvailable
                             && (root.source !== "bundled" || root.backend.bundledDataImported)))
                         && (root.step !== 4 || root.backend.activeDataAvailable)
                onClicked: root.backend.advanceOnboarding(
                    Math.min(root.step + 1, 4),
                    root.step === 2 ? root.source : "",
                    root.acceptedRisk,
                    root.step === 2 && root.source === "bundled" ? true : root.acceptedLicense,
                    root.acceptedTransfer
                )
            }
        }
    }
}
