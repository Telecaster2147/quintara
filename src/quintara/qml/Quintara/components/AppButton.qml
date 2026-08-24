import QtQuick
import QtQuick.Controls.Basic
import Quintara

Button {
    id: control
    property bool primary: false

    implicitHeight: Theme.controlHeight
    implicitWidth: Math.max(120, contentItem.implicitWidth + Theme.space4)
    activeFocusOnTab: true
    Accessible.name: text

    contentItem: Text {
        text: control.text
        color: !control.enabled ? Theme.textMuted : control.primary ? Theme.textOnPrimary : Theme.textPrimary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        opacity: control.enabled ? 1.0 : 0.55
        radius: Theme.radiusSmall
        color: !control.enabled ? Theme.surfaceInteractive : control.primary
               ? (control.hovered ? Theme.primaryHover : Theme.primary)
               : (control.hovered ? Theme.surfaceInteractive : Theme.surfaceRaised)
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.focus : Theme.outline
    }
}
