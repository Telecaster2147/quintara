pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import Quintara
import "pages"

Item {
    id: root
    objectName: "appShell"
    required property var backend
    signal openCsvDialog()
    signal openContentRootDialog()
    property bool compact: width < 1080
    readonly property string currentKey: backend ? backend.currentPage : "home"
    property var navItems: [
        {"key": "home", "label": qsTr("首页"), "glyph": "⌂"},
        {"key": "data", "label": qsTr("数据"), "glyph": "◫"},
        {"key": "universe", "label": qsTr("股票池"), "glyph": "◎"},
        {"key": "train", "label": qsTr("训练"), "glyph": "△"},
        {"key": "results", "label": qsTr("结果"), "glyph": "▥"},
        {"key": "history", "label": qsTr("历史"), "glyph": "◷"}
    ]

    function navigateLater(key) {
        Qt.callLater(function() {
            if (root.backend) root.backend.navigate(key)
        })
    }

    function performLater(key, target) {
        Qt.callLater(function() {
            if (root.backend) root.backend.perform(key, target)
        })
    }

    FileDialog {
        id: csvDialog
        title: qsTr("选择市场数据 CSV")
        nameFilters: [qsTr("CSV 文件 (*.csv)")]
        fileMode: FileDialog.OpenFile
        onAccepted: { if (root.backend) root.backend.importCsv(selectedFile.toString()) }
    }
    FileDialog {
        id: providerDialog
        title: qsTr("选择 Quintara 标准数据包")
        nameFilters: [qsTr("Quintara 数据包 (*.zip)")]
        fileMode: FileDialog.OpenFile
        onAccepted: { if (root.backend) root.backend.importProviderPackage(selectedFile.toString()) }
    }
    FileDialog {
        id: exportDialog
        title: qsTr("选择结果 CSV 保存位置")
        nameFilters: [qsTr("CSV 文件 (*.csv)")]
        fileMode: FileDialog.SaveFile
        onAccepted: root.requestExport(selectedFile.toString())
    }
    FolderDialog {
        id: contentRootDialog
        title: qsTr("选择新的 Quintara 数据目录")
        onAccepted: { if (root.backend) root.backend.migrateContentRoot(selectedFolder.toString()) }
    }

    property string pendingExportPath: ""
    function requestExport(value) {
        if (!root.backend) return
        if (root.backend.exportDestinationExists(value)) {
            root.pendingExportPath = value
            overwriteExportDialog.open()
        } else {
            root.backend.exportLatestResult(value)
        }
    }

    onOpenCsvDialog: csvDialog.open()
    onOpenContentRootDialog: contentRootDialog.open()

    ConfirmDialog {
        id: overwriteExportDialog
        heading: qsTr("文件已经存在")
        message: qsTr("覆盖前会保留原文件，新的 CSV 只有完整写入后才会替换它。")
        confirmText: qsTr("覆盖并导出")
        onAcceptedAction: {
            if (root.backend) root.backend.exportLatestResult(root.pendingExportPath, true)
            root.pendingExportPath = ""
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: root.compact ? Theme.navCompact : Theme.navWide
            color: Theme.surface
            border.color: Theme.outline

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.space2
                spacing: Theme.space1

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumHeight: 56
                    spacing: Theme.space1
                    Image {
                        Layout.preferredWidth: 38
                        Layout.preferredHeight: 38
                        source: Qt.resolvedUrl("../../assets/quintara-icon.png")
                        sourceSize.width: 38
                        sourceSize.height: 38
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        mipmap: true
                        Accessible.ignored: true
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: !root.compact
                        text: qsTr("Quintara")
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.sectionSize
                        font.weight: Font.DemiBold
                    }
                }

                Repeater {
                    model: root.navItems
                    delegate: Button {
                        id: navButton
                        required property var modelData
                        objectName: "nav-" + modelData.key
                        Layout.fillWidth: true
                        Layout.minimumHeight: 46
                        flat: true
                        activeFocusOnTab: true
                        Accessible.name: modelData.label
                        onClicked: root.navigateLater(modelData.key)
                        contentItem: RowLayout {
                            spacing: Theme.space2
                            Text {
                                text: navButton.modelData.glyph
                                color: navButton.modelData.key === root.currentKey ? Theme.primary : Theme.textMuted
                                font.pixelSize: 20
                                horizontalAlignment: Text.AlignHCenter
                                Layout.preferredWidth: 28
                                Accessible.ignored: true
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: !root.compact
                                text: navButton.modelData.label
                                color: navButton.modelData.key === root.currentKey ? Theme.primary : Theme.textPrimary
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.bodySize
                                font.weight: navButton.modelData.key === root.currentKey ? Font.DemiBold : Font.Normal
                            }
                        }
                        background: Rectangle {
                            radius: Theme.radiusSmall
                            color: navButton.modelData.key === root.currentKey
                                   ? Qt.alpha(Theme.primary, 0.12)
                                   : navButton.hovered ? Theme.surfaceInteractive : "transparent"
                            border.width: navButton.activeFocus ? 2 : 0
                            border.color: Theme.focus
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                Button {
                    id: settingsButton
                    Layout.fillWidth: true
                    Layout.minimumHeight: 46
                    flat: true
                    activeFocusOnTab: true
                    Accessible.name: qsTr("设置")
                    onClicked: Qt.callLater(function() { if (root.backend) root.backend.openSettings() })
                    contentItem: Text {
                        text: root.compact ? "⚙" : qsTr("设置")
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize
                        horizontalAlignment: root.compact ? Text.AlignHCenter : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: Theme.radiusSmall
                        color: settingsButton.hovered ? Theme.surfaceInteractive : "transparent"
                        border.width: settingsButton.activeFocus ? 2 : 0
                        border.color: Theme.focus
                    }
                }
                Button {
                    id: diagnosticsButton
                    Layout.fillWidth: true
                    Layout.minimumHeight: 46
                    flat: true
                    activeFocusOnTab: true
                    Accessible.name: qsTr("环境诊断")
                    onClicked: root.navigateLater("diagnostics")
                    contentItem: Text {
                        text: root.compact ? "ⓘ" : qsTr("环境诊断")
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize
                        horizontalAlignment: root.compact ? Text.AlignHCenter : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: Theme.radiusSmall
                        color: diagnosticsButton.hovered ? Theme.surfaceInteractive : "transparent"
                        border.width: diagnosticsButton.activeFocus ? 2 : 0
                        border.color: Theme.focus
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.canvas

            WorkspacePage {
                objectName: "workspacePage"
                anchors.fill: parent
                anchors.leftMargin: Theme.space4
                anchors.rightMargin: Theme.space4
                anchors.topMargin: Theme.space3
                anchors.bottomMargin: Theme.space3
                page: root.backend ? root.backend.currentPagePayload : ({})
                reducedMotion: root.backend ? root.backend.reducedMotion : false
                jobRunning: root.backend ? root.backend.jobRunning : false
                jobProgress: root.backend ? root.backend.jobProgress : 0
                jobStage: root.backend ? root.backend.jobStage : ""
                jobElapsedSeconds: root.backend ? root.backend.jobElapsedSeconds : 0
                jobLogs: root.backend ? root.backend.jobLogs : []
                themeMode: root.backend ? root.backend.themeMode : "system"
                onNavigate: target => root.navigateLater(target)
                onPrimaryAction: (key, target) => {
                    if (key === "import-csv") csvDialog.open()
                    else if (key === "import-bundled-data" && root.backend) root.backend.importBundledData()
                    else if (key === "import-provider-package") providerDialog.open()
                    else if (key === "export-result") exportDialog.open()
                    else root.performLater(key, target)
                }
                onSecondaryAction: (key, target) => {
                    if (key === "import-csv") csvDialog.open()
                    else if (key === "import-bundled-data" && root.backend) root.backend.importBundledData()
                    else if (key === "import-provider-package") providerDialog.open()
                    else if (key === "export-result") exportDialog.open()
                    else if (key === "choose-content-root") contentRootDialog.open()
                    else root.performLater(key, target)
                }
                onCancelJob: { if (root.backend) root.backend.cancelTraining() }
                onThemeRequested: value => { if (root.backend) root.backend.setTheme(value) }
                onReducedMotionRequested: value => { if (root.backend) root.backend.setReducedMotion(value) }
            }
        }
    }

}
