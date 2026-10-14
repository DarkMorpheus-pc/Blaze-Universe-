import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root

    property int page: 0
    property var disks: []
    property string target: ""
    property string statusText: "Diskler taranıyor…"
    property bool installing: false
    property bool installFinished: false

    function answersJson() {
        return JSON.stringify({
            hostname: hostname.text.trim(),
            locale: locale.currentValue,
            timezone: timezone.currentValue,
            keyboard_layout: keyboard.currentValue,
            username: username.text.trim(),
            full_name: fullName.text.trim()
        }, null, 2) + "\n"
    }

    function identityValid() {
        return /^[a-z_][a-z0-9_-]{0,31}$/.test(username.text)
            && /^[a-z0-9][a-z0-9.-]{0,62}$/.test(hostname.text)
            && fullName.text.trim().length > 0
            && password.text.length >= 8
            && password.text === passwordAgain.text
    }

    FileView {
        id: answersFile
        path: "/run/user/1000/solar-installer-answers.json"
        preload: false
        blockWrites: true
        atomicWrites: true
    }

    Process {
        id: probe
        running: true
        command: ["/usr/bin/solar-installer", "probe", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const all = JSON.parse(text)
                    root.disks = all.filter(d => d.eligible)
                    if (root.disks.length > 0) {
                        root.target = root.disks[0].path
                        root.statusText = root.disks.length + " uygun disk bulundu."
                    } else {
                        root.statusText = "Kuruluma uygun en az 16 GiB disk bulunamadı."
                    }
                } catch (error) {
                    root.statusText = "Disk listesi okunamadı: " + error
                }
            }
        }
        stderr: StdioCollector {
            onStreamFinished: if (text.trim()) root.statusText = text.trim()
        }
    }

    Process {
        id: installer
        stdinEnabled: true
        command: [
            "/usr/bin/sudo", "-n", "/usr/bin/solar-installer", "apply",
            "--target", root.target,
            "--confirm-erase", root.target,
            "--answers", answersFile.path,
            "--password-stdin"
        ]
        onStarted: {
            write(password.text)
            stdinEnabled = false
            password.text = ""
            passwordAgain.text = ""
        }
        onExited: (exitCode, exitStatus) => {
            root.installing = false
            root.installFinished = exitCode === 0
            root.statusText = exitCode === 0
                ? "BlazeOS kurulumu başarıyla tamamlandı. Sistemi yeniden başlatabilirsiniz."
                : "Kurulum başarısız oldu (kod " + exitCode + "). Günlük ayrıntılarını denetleyin."
        }
        stdout: SplitParser {
            onRead: data => root.statusText = data.trim()
        }
        stderr: SplitParser {
            onRead: data => { if (data.trim()) root.statusText = data.trim() }
        }
    }

    FloatingWindow {
        id: window
        title: "BlazeOS Kurulum Merkezi"
        implicitWidth: 900
        implicitHeight: 620
        color: "#0b1020"

        Rectangle {
            anchors.fill: parent
            color: "#0b1020"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 42
                spacing: 20

                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "BLAZE OS"; color: "#ff5b35"; font.pixelSize: 28; font.bold: true }
                    Item { Layout.fillWidth: true }
                    Text { text: "Adım " + (root.page + 1) + " / 6"; color: "#9ca8c7"; font.pixelSize: 16 }
                }

                ProgressBar { Layout.fillWidth: true; value: (root.page + 1) / 6 }

                StackLayout {
                    currentIndex: root.page
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    PagePane {
                        heading: "BlazeOS Native'a hoş geldiniz"
                        detail: "Kurucu diskinizi doğrular, sistemi atomik adımlarla yerleştirir ve BIOS ile UEFI önyüklemeyi birlikte hazırlar. Devam etmeden önce önemli dosyalarınızı yedekleyin."
                    }

                    PagePane {
                        heading: "Kurulum diski"
                        detail: "Seçtiğiniz diskin tamamı silinecektir. Canlı ortamın bulunduğu ve bağlı diskler otomatik olarak elenir."
                        ComboBox {
                            Layout.fillWidth: true
                            model: root.disks
                            textRole: "path"
                            onActivated: root.target = root.disks[currentIndex].path
                        }
                        Label { text: root.statusText; color: "#aeb9d6"; wrapMode: Text.Wrap }
                    }

                    PagePane {
                        heading: "Dil, bölge ve klavye"
                        detail: "Bu seçimler konsol, masaüstü ve saat dilimine birlikte uygulanır."
                        FormCombo { id: locale; label: "Dil"; choices: [{text:"Türkçe", value:"tr_TR.UTF-8"}, {text:"English (US)", value:"en_US.UTF-8"}] }
                        FormCombo { id: timezone; label: "Saat dilimi"; choices: [{text:"Europe/Istanbul", value:"Europe/Istanbul"}, {text:"UTC", value:"Etc/UTC"}, {text:"Europe/Berlin", value:"Europe/Berlin"}] }
                        FormCombo { id: keyboard; label: "Klavye"; choices: [{text:"Türkçe Q", value:"tr"}, {text:"US", value:"us"}, {text:"Deutsch", value:"de"}] }
                    }

                    PagePane {
                        heading: "Hesabınız"
                        detail: "Parolanız yalnızca kurucu sürecine aktarılır; komut satırında, yanıtlarda veya günlüklerde tutulmaz."
                        FormField { id: fullName; label: "Ad soyad"; placeholder: "Blaze Kullanıcısı" }
                        FormField { id: username; label: "Kullanıcı adı"; placeholder: "blaze" }
                        FormField { id: hostname; label: "Bilgisayar adı"; placeholder: "blaze-pc" }
                        FormField { id: password; label: "Parola"; secret: true }
                        FormField { id: passwordAgain; label: "Parolayı doğrula"; secret: true }
                        Label { visible: !root.identityValid(); text: "Geçerli adlar ve en az 8 karakterlik eşleşen parolalar gerekli."; color: "#ff9c85" }
                    }

                    PagePane {
                        heading: "Son kontrol"
                        detail: "Hedef: " + root.target + "\nKullanıcı: " + username.text + "\nBilgisayar: " + hostname.text + "\nBölge: " + locale.currentValue + " · " + timezone.currentValue
                        CheckBox { id: eraseConfirmed; text: "Seçili diskin tamamen silineceğini anlıyorum." }
                    }

                    PagePane {
                        heading: root.installFinished ? "Kurulum tamamlandı" : "BlazeOS kuruluyor"
                        detail: root.statusText
                        BusyIndicator { running: root.installing; visible: running; Layout.alignment: Qt.AlignHCenter }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        text: "Geri"
                        enabled: root.page > 0 && !root.installing
                        onClicked: root.page--
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: root.page === 4 ? "Kurulumu başlat" : "Devam"
                        visible: root.page < 5
                        enabled: !root.installing
                            && (root.page !== 1 || root.target.length > 0)
                            && (root.page !== 3 || root.identityValid())
                            && (root.page !== 4 || eraseConfirmed.checked)
                        onClicked: {
                            if (root.page === 4) {
                                answersFile.setText(root.answersJson())
                                root.installing = true
                                root.page = 5
                                root.statusText = "Kurulum motoru başlatılıyor…"
                                installer.running = true
                            } else {
                                root.page++
                            }
                        }
                    }
                }
            }
        }
    }
}
