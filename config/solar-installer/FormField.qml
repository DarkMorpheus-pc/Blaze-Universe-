import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    property string label
    property string placeholder: ""
    property bool secret: false
    property alias text: input.text
    Label { text: parent.label; color: "#dbe2f5"; Layout.preferredWidth: 160 }
    TextField {
        id: input
        Layout.fillWidth: true
        placeholderText: parent.placeholder
        echoMode: parent.secret ? TextInput.Password : TextInput.Normal
    }
}
