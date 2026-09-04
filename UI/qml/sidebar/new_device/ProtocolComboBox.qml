pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import UI

StandardComboBox {
    id: root
    Layout.fillWidth: true

    // Biến để chặn tự động đổi Port khi đang nạp dữ liệu cũ (Edit Mode)
    property bool isEditMode: false

    // Tín hiệu bắn ra ngoài khi Protocol thay đổi
    signal portAutoChanged(string newPort)

    model: ["SSH", "TELNET", "NETCONF", "RESTCONF"]

    // Xử lý tự động điền Port khi đổi Protocol
    onCurrentTextChanged: {
        if (!isEditMode || activeFocus) {
            if (currentText === "SSH") portAutoChanged("22")
            else if (currentText === "TELNET") portAutoChanged("23")
            else if (currentText === "NETCONF") portAutoChanged("830")
            else if (currentText === "RESTCONF") portAutoChanged("443")
        }
    }
}