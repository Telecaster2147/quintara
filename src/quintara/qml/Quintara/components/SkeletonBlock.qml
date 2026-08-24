import QtQuick
import Quintara

Rectangle {
    id: root
    property bool reducedMotion: false
    implicitHeight: 88
    radius: Theme.radiusMedium
    color: Theme.surfaceInteractive

    SequentialAnimation on scale {
        running: root.visible && !root.reducedMotion
        loops: Animation.Infinite
        ScaleAnimator { from: 1.0; to: 0.985; duration: 650; easing.type: Easing.InOutQuad }
        ScaleAnimator { from: 0.985; to: 1.0; duration: 650; easing.type: Easing.InOutQuad }
    }
    Accessible.ignored: true
}
