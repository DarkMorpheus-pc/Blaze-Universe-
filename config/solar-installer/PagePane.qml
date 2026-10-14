import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    property string heading
    property string detail
    spacing: 18

    Label { text: parent.heading; color: "#f5f7ff"; font.pixelSize: 30; font.bold: true }
    Label {
        text: parent.detail
        color: "#aeb9d6"
        font.pixelSize: 17
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }
}
