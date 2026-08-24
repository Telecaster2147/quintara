pragma Singleton
import QtQuick

QtObject {
    property bool darkMode: false
    readonly property color canvas: darkMode ? "#071426" : "#F4F7FB"
    readonly property color surface: darkMode ? "#0D2037" : "#FFFFFF"
    readonly property color surfaceRaised: darkMode ? "#132A44" : "#F9FBFE"
    readonly property color surfaceInteractive: darkMode ? "#17334F" : "#EDF5FA"
    readonly property color textPrimary: darkMode ? "#F3F7FB" : "#10243D"
    readonly property color textMuted: darkMode ? "#A9B8C9" : "#596A7E"
    readonly property color primary: darkMode ? "#45C7D8" : "#087E8B"
    readonly property color primaryHover: darkMode ? "#62D5E3" : "#076D78"
    readonly property color textOnPrimary: "#FFFFFF"
    readonly property color accent: "#F4B942"
    readonly property color success: darkMode ? "#6BD6A0" : "#237A50"
    readonly property color warning: darkMode ? "#F3C66B" : "#9A6200"
    readonly property color error: darkMode ? "#FF8C8C" : "#B4232C"
    readonly property color outline: darkMode ? "#29435F" : "#D8E1EB"
    readonly property color focus: darkMode ? "#F4B942" : "#075E73"
    readonly property color shadow: darkMode ? "#80000000" : "#26071F3F"

    readonly property int space1: 8
    readonly property int space2: 16
    readonly property int space3: 24
    readonly property int space4: 32
    readonly property int radiusSmall: 10
    readonly property int radiusMedium: 16
    readonly property int radiusLarge: 24
    readonly property int controlHeight: 44
    readonly property int clickTarget: 44
    readonly property int motionFast: 120
    readonly property int motionNormal: 180
    readonly property int navWide: 224
    readonly property int navCompact: 76
    readonly property int pageMaxWidth: 1180
    readonly property int bodySize: 16
    readonly property int captionSize: 13
    readonly property int sectionSize: 20
    readonly property int titleSize: 28

    readonly property string fontFamily: Qt.platform.os === "windows"
                                                ? "Segoe UI Variable"
                                                : "Noto Sans CJK SC"
    readonly property var chineseFontFallbacks: ["Segoe UI Variable", "Microsoft YaHei UI", "Noto Sans CJK SC", "sans-serif"]
}
