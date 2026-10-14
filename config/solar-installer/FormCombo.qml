import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    property string label
    property var choices: []
    property alias currentValue: input.currentValue
    Label { text: parent.label; color: "#dbe2f5"; Layout.preferredWidth: 160 }
    ComboBox {
        id: input
        Layout.fillWidth: true
        model: parent.choices
        textRole: "text"
        valueRole: "value"
    }
}
