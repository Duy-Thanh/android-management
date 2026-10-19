import sys
import subprocess
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit, QTabWidget,
    QGroupBox, QFormLayout, QMessageBox, QComboBox, QFileDialog, QProgressBar
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont

# Xác định thư mục bin cục bộ của App
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_SDK_DIR = os.path.join(BASE_DIR, "bin", "platform-tools")

# Tự động Inject PATH cục bộ lên đầu môi trường OS
if os.path.exists(LOCAL_SDK_DIR):
    os.environ["PATH"] = LOCAL_SDK_DIR + os.path.pathsep + os.environ.get("PATH", "")

class SetupSDKThread(QThread):
    """Thread tải và giải nén Platform-Tools từ Google"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def run(self):
        try:
            # URL chính chủ từ Google
            if os.name == 'nt':
                url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
            else:
                url = "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"

            zip_path = os.path.join(BASE_DIR, "platform-tools.zip")
            bin_dir = os.path.join(BASE_DIR, "bin")
            os.makedirs(bin_dir, exist_ok=True)

            self.log_signal.emit(f"[SETUP]: Đang tải Platform-Tools từ Google ({url})...")

            # Tải file có báo % tiến trình
            def hook(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                self.progress_signal.emit(min(100, percent))

            urllib.request.urlretrieve(url, zip_path, reporthook=hook)
            self.log_signal.emit("[SETUP]: Giải nén tập tin...")

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(bin_dir)

            # Xóa file zip rác
            if os.path.exists(zip_path):
                os.remove(zip_path)

            # Cấp quyền execute trên Linux/macOS
            if os.name != 'nt':
                for binary in ["adb", "fastboot", "mke2fs"]:
                    b_path = os.path.join(LOCAL_SDK_DIR, binary)
                    if os.path.exists(b_path):
                        os.chmod(b_path, 0o755)

            # Cập nhật Runtime PATH
            os.environ["PATH"] = LOCAL_SDK_DIR + os.path.pathsep + os.environ.get("PATH", "")

            self.log_signal.emit("[SETUP HOÀN TẤT]: Đã cài đặt Android SDK Platform-Tools thành công!")
            self.finished_signal.emit(True)

        except Exception as e:
            self.log_signal.emit(f"[LỖI SETUP]: {str(e)}")
            self.finished_signal.emit(False)



class CommandThread(QThread):
    """Thread riêng để chạy CLI mượt mà không làm đơ UI"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, command: list[str]):
        super().__init__()
        self.command = command

    def run(self):
        try:
            # Ép Python không buffer output
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Gộp stderr vào stdout
                text=True,
                bufsize=1,  # Line buffered
                env=env,
                shell=(os.name == 'nt')
            )

            # Đọc từng dòng realtime
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.output_signal.emit(line.rstrip())

            process.stdout.close()
            rc = process.wait()
            self.finished_signal.emit(rc)
        except Exception as e:
            self.output_signal.emit(f"[LỖI THI HÀNH]: {str(e)}")
            self.finished_signal.emit(-1)


class ADBFastbootGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ADB & Fastboot Toolkit Wrapper v2.0")
        self.resize(900, 750)

        self.init_ui()
        self.refresh_devices()  # Tự động quét thiết bị khi mở app

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ------------------ TOP BAR: SETUP SDK & DEVICE SELECTOR ------------------
        top_group = QGroupBox("Cấu Hình Môi Trường & Thiết Bị")
        top_layout = QVBoxLayout(top_group)

        # Hàng 1: Nút Setup SDK tự động
        sdk_layout = QHBoxLayout()
        self.btn_setup_sdk = QPushButton("Tải & Auto-Setup Platform-Tools (Google)")
        self.btn_setup_sdk.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_setup_sdk.clicked.connect(self.start_sdk_setup)

        self.sdk_progress = QProgressBar()
        self.sdk_progress.setVisible(False)

        sdk_layout.addWidget(self.btn_setup_sdk)
        sdk_layout.addWidget(self.sdk_progress)
        top_layout.addLayout(sdk_layout)

        # ------------------ KHU VỰC THIẾT BỊ (DEVICE SELECTOR) ------------------
        device_group = QGroupBox("Kết Nối & Thiết Bị")
        device_layout = QHBoxLayout(device_group)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(250)
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)

        btn_refresh = QPushButton("Làm Mới Thiết Bị")
        btn_refresh.clicked.connect(self.refresh_devices)

        self.lbl_selected_device = QLabel("Đang quét...")
        self.lbl_selected_device.setStyleSheet("font-weight: bold; color: #3498db;")

        device_layout.addWidget(QLabel("Chọn Thiết Bị Target:"))
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(btn_refresh)
        device_layout.addStretch()
        device_layout.addWidget(self.lbl_selected_device)

        main_layout.addWidget(device_group)

        # ------------------ TAB INTERFACE ------------------
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_adb_tab(), "ADB Management")
        self.tabs.addTab(self.create_fastboot_tab(), "Fastboot Operations")
        self.tabs.addTab(self.create_advanced_tab(), "ADB Sideload & Advanced")
        main_layout.addWidget(self.tabs)

        # ------------------ CONSOLE LOG ------------------
        log_group = QGroupBox("Console Output Log")
        log_layout = QVBoxLayout(log_group)

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Courier New", 10))
        self.console_output.setStyleSheet("background-color: #1a1a1a; color: #2ecc71;")
        log_layout.addWidget(self.console_output)

        clear_btn = QPushButton("Xóa Log")
        clear_btn.clicked.connect(self.console_output.clear)
        log_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

        main_layout.addWidget(log_group)

    def start_sdk_setup(self):
        """Khởi chạy Thread tải SDK"""
        self.btn_setup_sdk.setEnabled(False)
        self.sdk_progress.setValue(0)
        self.sdk_progress.setVisible(True)

        self.setup_thread = SetupSDKThread()
        self.setup_thread.log_signal.connect(self.append_log)
        self.setup_thread.progress_signal.connect(self.sdk_progress.setValue)
        self.setup_thread.finished_signal.connect(self.on_sdk_setup_finished)
        self.setup_thread.start()

    def on_sdk_setup_finished(self, success: bool):
        self.btn_setup_sdk.setEnabled(True)
        self.sdk_progress.setVisible(False)
        if success:
            QMessageBox.information(self, "Thành công", "Đã cài đặt SDK Platform-Tools chính chủ thành công!")
            self.refresh_devices()
        else:
            QMessageBox.critical(self, "Lỗi", "Không thể tải Platform-Tools. Kiểm tra lại kết nối mạng!")

    def open_windows_driver_link(self):
        """Mở trang tải Google USB Driver nếu chạy trên Windows"""
        if os.name == 'nt':
            import webbrowser
            webbrowser.open("https://developer.android.com/studio/run/win-usb")

    # ==================== CÁC TAB CHỨC NĂNG ====================

    def create_adb_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 1. Thao Tác Cơ Bản
        basic_group = QGroupBox("Thao Tác Cơ Bản")
        basic_layout = QHBoxLayout(basic_group)

        btn_reboot = QPushButton("Reboot System")
        btn_reboot.clicked.connect(lambda: self.run_adb_cmd(["reboot"]))

        btn_reboot_bootloader = QPushButton("Reboot to Bootloader")
        btn_reboot_bootloader.clicked.connect(lambda: self.run_adb_cmd(["reboot", "bootloader"]))

        btn_reboot_recovery = QPushButton("Reboot to Recovery")
        btn_reboot_recovery.clicked.connect(lambda: self.run_adb_cmd(["reboot", "recovery"]))

        basic_layout.addWidget(btn_reboot)
        basic_layout.addWidget(btn_reboot_bootloader)
        basic_layout.addWidget(btn_reboot_recovery)
        layout.addWidget(basic_group)

        # 2. Quản Lý File (Push / Pull)
        file_group = QGroupBox("Truyền Tải File & Thư Mục (Push / Pull)")
        file_layout = QFormLayout(file_group)

        self.local_path_input = QLineEdit()
        btn_browse_local = QPushButton("Chọn File/Foler...")
        btn_browse_local.clicked.connect(self.browse_local_path)

        local_path_layout = QHBoxLayout()
        local_path_layout.addWidget(self.local_path_input)
        local_path_layout.addWidget(btn_browse_local)

        self.remote_path_input = QLineEdit()
        self.remote_path_input.setPlaceholderText("Ví dụ: /sdcard/Download/ hoặc /data/local/tmp/")

        btn_push = QPushButton("Push lên Thiết Bị (Local -> Remote)")
        btn_push.setStyleSheet("background-color: #27ae60; color: white;")
        btn_push.clicked.connect(self.execute_push)

        btn_pull = QPushButton("Pull về Máy Tính (Remote -> Local)")
        btn_pull.setStyleSheet("background-color: #2980b9; color: white;")
        btn_pull.clicked.connect(self.execute_pull)

        file_buttons = QHBoxLayout()
        file_buttons.addWidget(btn_push)
        file_buttons.addWidget(btn_pull)

        file_layout.addRow("Đường Dẫn Trên PC:", local_path_layout)
        file_layout.addRow("Đường Dẫn Trên Điện Thoại:", self.remote_path_input)
        file_layout.addRow("", file_buttons)
        layout.addWidget(file_group)

        # 3. Quản Lý Ứng Dụng (Cài APK)
        app_group = QGroupBox("Quản Lý Ứng Dụng (APK)")
        app_layout = QHBoxLayout(app_group)

        self.apk_input = QLineEdit()
        self.apk_input.setPlaceholderText("Chọn hoặc kéo thả đường dẫn file .apk")
        btn_browse_apk = QPushButton("Duyệt APK")
        btn_browse_apk.clicked.connect(self.browse_apk_path)
        btn_install = QPushButton("Cài Đặt APK")
        btn_install.setStyleSheet("font-weight: bold;")
        btn_install.clicked.connect(self.execute_install_apk)

        app_layout.addWidget(self.apk_input)
        app_layout.addWidget(btn_browse_apk)
        app_layout.addWidget(btn_install)
        layout.addWidget(app_group)

        # 4. Custom Shell Command
        shell_group = QGroupBox("Thực Thi Lệnh Shell Tự Do")
        shell_layout = QHBoxLayout(shell_group)
        self.shell_input = QLineEdit()
        self.shell_input.setPlaceholderText("Ví dụ: pm list packages | getprop ro.product.model")
        btn_shell = QPushButton("Chạy ADB Shell")
        btn_shell.clicked.connect(self.execute_shell_command)

        shell_layout.addWidget(self.shell_input)
        shell_layout.addWidget(btn_shell)
        layout.addWidget(shell_group)

        layout.addStretch()
        return tab

    def create_fastboot_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        fb_basic_group = QGroupBox("Fastboot Cơ Bản")
        fb_basic_layout = QHBoxLayout(fb_basic_group)

        btn_fb_devices = QPushButton("Nhận Diện Thiết Bị (Fastboot Devices)")
        btn_fb_devices.clicked.connect(lambda: self.run_cmd(["fastboot", "devices"]))

        btn_getvar = QPushButton("Xem Toàn Bộ Thông Tin (Getvar All)")
        btn_getvar.clicked.connect(lambda: self.run_fastboot_cmd(["getvar", "all"]))

        fb_basic_layout.addWidget(btn_fb_devices)
        fb_basic_layout.addWidget(btn_getvar)
        layout.addWidget(fb_basic_group)

        # 2. Bổ Sung: Các Chế Độ Khởi Động Lại (Reboot Options)
        reboot_group = QGroupBox("Điều Hướng Chế Độ Khởi Động Lại")
        reboot_layout = QHBoxLayout(reboot_group)

        btn_reboot_sys = QPushButton("Reboot System")
        btn_reboot_sys.clicked.connect(lambda: self.run_fastboot_cmd(["reboot"]))

        btn_reboot_rec = QPushButton("Reboot Recovery")
        btn_reboot_rec.setStyleSheet("background-color: #d35400; color: white; font-weight: bold;")
        btn_reboot_rec.clicked.connect(lambda: self.run_fastboot_cmd(["reboot", "recovery"]))

        btn_reboot_bl = QPushButton("Reboot Bootloader")
        btn_reboot_bl.clicked.connect(lambda: self.run_fastboot_cmd(["reboot", "bootloader"]))

        btn_reboot_fb = QPushButton("Reboot Fastbootd")
        btn_reboot_fb.clicked.connect(lambda: self.run_fastboot_cmd(["reboot", "fastboot"]))

        reboot_layout.addWidget(btn_reboot_sys)
        reboot_layout.addWidget(btn_reboot_rec)
        reboot_layout.addWidget(btn_reboot_bl)
        reboot_layout.addWidget(btn_reboot_fb)
        layout.addWidget(reboot_group)

        # 3. Bổ Sung: Quản Lý Active Slot (A/B Partition)
        slot_group = QGroupBox("Quản Lý Slot A/B (A/B Seamless)")
        slot_layout = QHBoxLayout(slot_group)

        btn_slot_a = QPushButton("Chuyển Sang Slot A")
        btn_slot_a.clicked.connect(lambda: self.run_fastboot_cmd(["--set-active=a"]))

        btn_slot_b = QPushButton("Chuyển Sang Slot B")
        btn_slot_b.clicked.connect(lambda: self.run_fastboot_cmd(["--set-active=b"]))

        slot_layout.addWidget(btn_slot_a)
        slot_layout.addWidget(btn_slot_b)
        layout.addWidget(slot_group)

        flash_group = QGroupBox("Flash Phân Vùng (Fastboot Flash)")
        flash_layout = QFormLayout(flash_group)

        self.partition_input = QLineEdit()
        self.partition_input.setPlaceholderText("Ví dụ: boot, recovery, system, product, vendor...")

        self.img_path_input = QLineEdit()
        self.img_path_input.setPlaceholderText("Đường dẫn đến file .img")
        btn_browse_img = QPushButton("Chọn File Image...")
        btn_browse_img.clicked.connect(self.browse_img_path)

        img_layout = QHBoxLayout()
        img_layout.addWidget(self.img_path_input)
        img_layout.addWidget(btn_browse_img)

        btn_flash = QPushButton("Tiến Hành Flash Partition")
        btn_flash.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        btn_flash.clicked.connect(self.execute_flash)

        flash_layout.addRow("Tên Phân Vùng (Partition):", self.partition_input)
        flash_layout.addRow("File Hình Ảnh Image (.img):", img_layout)
        flash_layout.addRow("", btn_flash)
        layout.addWidget(flash_group)

        layout.addStretch()
        return tab

    def run_fastboot_cmd(self, args: list[str]):
        """Helper gọi fastboot chuẩn có gắn Device ID (-s)"""
        dev_id = self.get_selected_device_id()
        cmd = ["fastboot"]
        if dev_id:
            cmd.extend(["-s", dev_id])
        cmd.extend(args)
        self.run_cmd(cmd)

    def create_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        sideload_group = QGroupBox("ADB Sideload (Nạp ROM / OTA qua Recovery)")
        sideload_layout = QFormLayout(sideload_group)

        self.ota_zip_input = QLineEdit()
        self.ota_zip_input.setPlaceholderText("Chọn file nén OTA (.zip)")
        btn_browse_zip = QPushButton("Chọn File ZIP...")
        btn_browse_zip.clicked.connect(self.browse_zip_path)

        zip_layout = QHBoxLayout()
        zip_layout.addWidget(self.ota_zip_input)
        zip_layout.addWidget(btn_browse_zip)

        btn_reboot_sideload = QPushButton("1. Đưa ĐT Vào Chế Độ Sideload (Reboot Sideload)")
        btn_reboot_sideload.clicked.connect(lambda: self.run_adb_cmd(["reboot", "sideload"]))

        btn_sideload = QPushButton("2. Tiến Hành Sideload Lên Thiết Bị")
        btn_sideload.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold;")
        btn_sideload.clicked.connect(self.execute_sideload)

        sideload_layout.addRow("File ROM/Update (.zip):", zip_layout)
        sideload_layout.addRow("Bước Chuẩn Bị:", btn_reboot_sideload)
        sideload_layout.addRow("Bước Thực Thi:", btn_sideload)

        layout.addWidget(sideload_group)
        layout.addStretch()
        return tab

    # ==================== FILE DIALOG BROWSERS ====================

    def browse_local_path(self):
        # Cho phép chọn cả file hoặc thư mục bằng cách click "Mở"
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        # Nếu muốn cho phép chọn cả folder
        path = dialog.getExistingDirectory(self, "Chọn Thư Mục") if QMessageBox.question(self, "Lựa chọn", "Bạn muốn chọn thư mục (Yes) hay tập tin (No)?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes else dialog.getOpenFileName(self, "Chọn File")[0]
        if path:
            self.local_path_input.setText(path)

    def browse_apk_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file ứng dụng Android", "", "APK files (*.apk)")
        if file_path:
            self.apk_input.setText(file_path)

    def browse_img_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn phân vùng ảnh", "", "Image files (*.img *.bin)")
        if file_path:
            self.img_path_input.setText(file_path)

    def browse_zip_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file nén để nâng cấp", "", "ZIP files (*.zip)")
        if file_path:
            self.ota_zip_input.setText(file_path)

    # ==================== ĐIỀU PHỐI VÀ CHẠY LỆNH ====================

    def refresh_devices(self):
        """Quét cả thiết bị ADB và Fastboot"""
        self.device_combo.clear()
        found_devices = []

        # 1. Quét ADB
        try:
            res_adb = subprocess.run(["adb", "devices"], capture_output=True, text=True, shell=(os.name == 'nt'))
            for line in res_adb.stdout.strip().split("\n")[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        found_devices.append((parts[0], f"ADB: {parts[1]}"))
        except Exception:
            pass

        # 2. Quét Fastboot
        try:
            res_fb = subprocess.run(["fastboot", "devices"], capture_output=True, text=True, shell=(os.name == 'nt'))
            for line in res_fb.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        found_devices.append((parts[0], "Fastboot"))
        except Exception:
            pass

        # Update ComboBox
        if found_devices:
            for dev_id, mode in found_devices:
                self.device_combo.addItem(f"{dev_id} [{mode}]", dev_id)
            self.lbl_selected_device.setText(f"Active: {found_devices[0][0]}")
        else:
            self.device_combo.addItem("Không tìm thấy thiết bị nào")
            self.lbl_selected_device.setText("No Device")

    def on_device_selected(self, index):
        selected_id = self.device_combo.itemData(index)
        if selected_id:
            self.lbl_selected_device.setText(f"Active: {selected_id}")
        else:
            self.lbl_selected_device.setText("Chờ thiết bị...")

    def get_selected_device_id(self) -> str:
        """Lấy device id được chọn từ QComboBox"""
        return self.device_combo.itemData(self.device_combo.currentIndex())

    def run_adb_cmd(self, command_args: list[str]):
        """Bọc lệnh adb với option thiết bị cụ thể target -s"""
        dev_id = self.get_selected_device_id()
        if not dev_id:
            self.show_warn("Chưa chọn thiết bị để chạy lệnh!")
            return

        # Thêm tiền tố 'adb -s <id>'
        full_command = ["adb", "-s", dev_id] + command_args
        self.run_cmd(full_command)

    def run_cmd(self, command: list[str]):
        """Khởi tạo sub-thread để thực thi cmd"""
        cmd_str = " ".join(command)
        self.console_output.append(f"\n[RUNNING]: {cmd_str}\n" + "-" * 50)

        self.thread = CommandThread(command)
        self.thread.output_signal.connect(self.append_log)
        self.thread.finished_signal.connect(
            lambda code: self.append_log(f"\n[KẾT THÚC LỆNH VỚI MÃ]: {code}\n" + "=" * 50)
        )
        self.thread.start()

    def append_log(self, text: str):
        self.console_output.append(text)

    def show_warn(self, msg: str):
        QMessageBox.warning(self, "Thông Báo", msg)

    # ==================== EXECUTE LOGIC ====================

    def execute_push(self):
        local = self.local_path_input.text().strip()
        remote = self.remote_path_input.text().strip()
        if not local or not remote:
            self.show_warn("Hãy nhập đầy đủ đường dẫn Local và Remote!")
            return
        self.run_adb_cmd(["push", local, remote])

    def execute_pull(self):
        local = self.local_path_input.text().strip()
        remote = self.remote_path_input.text().strip()
        if not local or not remote:
            self.show_warn("Hãy nhập đầy đủ đường dẫn Local và Remote!")
            return
        self.run_adb_cmd(["pull", remote, local])

    def execute_install_apk(self):
        apk = self.apk_input.text().strip()
        if not apk:
            self.show_warn("Bạn chưa chọn file APK cần cài đặt!")
            return
        self.run_adb_cmd(["install", "-r", "-d", apk])

    def execute_shell_command(self):
        cmd = self.shell_input.text().strip()
        if not cmd:
            self.show_warn("Hãy nhập câu lệnh shell muốn thực thi!")
            return
        self.run_adb_cmd(["shell", cmd])

    def execute_flash(self):
        part = self.partition_input.text().strip()
        img = self.img_path_input.text().strip()
        if not part or not img:
            self.show_warn("Chưa nhập đủ thông tin phân vùng hoặc file Flash Image!")
            return
        self.run_fastboot_cmd(["flash", part, img])

    def execute_sideload(self):
        zip_file = self.ota_zip_input.text().strip()
        if not zip_file:
            self.show_warn("Hãy chọn file .zip muốn sideload trước!")
            return
        # Lệnh ADB Sideload
        self.run_adb_cmd(["sideload", zip_file])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ADBFastbootGUI()
    window.show()
    sys.exit(app.exec())
