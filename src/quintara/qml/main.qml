import QtQuick
import QtQuick.Controls
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
    }
}
