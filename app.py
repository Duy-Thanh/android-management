import sys
import subprocess
import os
import shutil
import zipfile
import urllib.request
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit, QTabWidget,
    QGroupBox, QFormLayout, QMessageBox, QComboBox, QFileDialog, QProgressBar
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont

# Identify the app's local bin directory
if getattr(sys, 'frozen', False):
    # If running from a PyInstaller-packaged binary file
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # If running from the original app.py script file
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOCAL_SDK_DIR = os.path.join(BASE_DIR, "bin", "platform-tools")

# Automatically inject the local PATH to the beginning of the OS environment
if os.path.exists(LOCAL_SDK_DIR):
    os.environ["PATH"] = LOCAL_SDK_DIR + os.path.pathsep + os.environ.get("PATH", "")

class SDKDoctorThread(QThread):
    """Troubleshooting thread for Platform-Tools & USB environment issues: automated diagnosis and error resolution"""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def run(self):
        try:
            self.log_signal.emit("\n" + "=" * 50)
            self.log_signal.emit("[DOCTOR]: STARTING DIAGNOSIS AND ENVIRONMENT TROUBLESHOOTING...")
            self.log_signal.emit("=" * 50)

            # 1. Check Binary
            adb_path = shutil.which("adb")
            fb_path = shutil.which("fastboot")
            self.log_signal.emit(f"-> [Check ADB]: {adb_path if adb_path else 'NOT FOUND ❌'}")
            self.log_signal.emit(f"-> [Check Fastboot]: {fb_path if fb_path else 'NOT FOUND ❌'}")

            # 2. Clear Zombie Processes
            self.log_signal.emit("-> [Doctor Fix]: Cleaning up processes (fastboot, adb)...")
            try:
                # Kill fastboot kẹt nếu chạy trên Linux/macOS
                if os.name != 'nt':
                    subprocess.run(["killall", "-q", "-9", "fastboot"], timeout=2)
                    subprocess.run(["killall", "-q", "-9", "adbd"], timeout=2)
                    subprocess.run(["killall", "-q", "-9", "adb"], timeout=2)
                else:
                    # Trên Windows dùng taskkill nếu cần
                    subprocess.run(["taskkill", "/F", "/IM", "fastboot.exe"], capture_output=True)
                    subprocess.run(["taskkill", "/F", "/IM", "adbd.exe"], capture_output=True)
                    subprocess.run(["taskkill", "/F", "/IM", "adb.exe"], capture_output=True)
            except Exception:
                pass

            # 3. Reset ADB Daemon Server
            self.log_signal.emit("-> [Doctor Fix]: Restart the ADB Daemon Server...")
            subprocess.run(["adb", "kill-server"], capture_output=True)
            subprocess.run(["adb", "start-server"], capture_output=True)

            # 4. Check Linux USB Autosuspend
            if os.name != 'nt' and os.path.exists("/sys/module/usbcore/parameters/autosuspend"):
                try:
                    with open("/sys/module/usbcore/parameters/autosuspend", "r") as f:
                        val = f.read().strip()
                    if val != "-1":
                        self.log_signal.emit("-> [WARNING]: USB Autosuspend is ENABLED (Likely to cause USB endpoint stalls")
                        self.log_signal.emit("   Run this command from the terminal to permanently fix it: echo -1 | sudo tee /sys/module/usbcore/parameters/autosuspend")
                    else:
                        self.log_signal.emit("-> [Check Autosuspend]: USB Autosuspend is DISABLED")
                except Exception:
                    pass

            # 5. Fix Permissions on Linux/macOS
            if os.name != 'nt' and os.path.exists(LOCAL_SDK_DIR):
                self.log_signal.emit("-> [Doctor Fix]: Restore `chmod +x` permissions for local binaries...")
                for binary in ["adb", "fastboot", "mke2fs"]:
                    b_path = os.path.join(LOCAL_SDK_DIR, binary)
                    if os.path.exists(b_path):
                        os.chmod(b_path, 0o755)

            self.log_signal.emit("\n[DOCTOR]: Diagnosis complete! The environment has been 100% cleared")
            self.finished_signal.emit(True)

        except Exception as e:
            self.log_signal.emit(f"[DOCTOR FAILED]: {str(e)}")
            self.finished_signal.emit(False)

class SetupSDKThread(QThread):
    """Thread for downloading and extracting platform-tools from Google"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def run(self):
        try:
            # Official URL from Google
            if os.name == 'nt':
                url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
            else:
                url = "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"

            zip_path = os.path.join(BASE_DIR, "platform-tools.zip")
            bin_dir = os.path.join(BASE_DIR, "bin")
            os.makedirs(bin_dir, exist_ok=True)

            self.log_signal.emit("[SETUP]: Downloading ...")

            # Download file with progress percentage indicator
            def hook(count, block_size, total_size):
                if total_size > 0:
                    percent = int(count * block_size * 100 / total_size)
                    self.progress_signal.emit(min(100, percent))

            urllib.request.urlretrieve(url, zip_path, reporthook=hook)
            self.log_signal.emit("[SETUP]: Ending orphan processes...")
            try:
                # Kill fastboot kẹt nếu chạy trên Linux/macOS
                if os.name != 'nt':
                    subprocess.run(["killall", "-q", "-9", "fastboot"], timeout=2)
                    subprocess.run(["killall", "-q", "-9", "adbd"], timeout=2)
                    subprocess.run(["killall", "-q", "-9", "adb"], timeout=2)
                else:
                    # Trên Windows dùng taskkill nếu cần
                    subprocess.run(["taskkill", "/F", "/IM", "fastboot.exe"], capture_output=True)
                    subprocess.run(["taskkill", "/F", "/IM", "adbd.exe"], capture_output=True)
                    subprocess.run(["taskkill", "/F", "/IM", "adb.exe"], capture_output=True)
            except Exception:
                pass

            self.log_signal.emit("[SETUP]: Cleaning old directories")
            try:
                target_bin = os.path.join(BASE_DIR, "bin")
                if os.path.exists(target_bin):
                    shutil.rmtree(target_bin, ignore_errors=True)
            except Exception as e:
                self.log_signal.emit(f"[WARN]: Cannot clean old directory: {str(e)}")

            self.log_signal.emit("[SETUP]: Extract the file...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(bin_dir)

            # Delete junk zip files
            if os.path.exists(zip_path):
                os.remove(zip_path)

            # Granting execute permissions on Linux/macOS
            if os.name != 'nt':
                for binary in ["adb", "fastboot", "mke2fs"]:
                    b_path = os.path.join(LOCAL_SDK_DIR, binary)
                    if os.path.exists(b_path):
                        os.chmod(b_path, 0o755)

            # Cập nhật Runtime PATH
            os.environ["PATH"] = LOCAL_SDK_DIR + os.path.pathsep + os.environ.get("PATH", "")

            self.log_signal.emit("[SETUP COMPLETED]: Dependencies installed successfully!")
            self.finished_signal.emit(True)

        except Exception as e:
            self.log_signal.emit(f"[SETUP FAILED]: {str(e)}")
            self.finished_signal.emit(False)

class CommandThread(QThread):
    """A separate thread to ensure smooth CLI execution without freezing the UI"""
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, command: list[str]):
        super().__init__()
        self.command = command

    def run(self):
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                shell=(os.name == 'nt')
            )

            # Assert to Pyright that `process.stdout` is never `None`.
            if process.stdout is not None:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        self.output_signal.emit(line.rstrip())
                process.stdout.close()

            rc = process.wait()
            self.finished_signal.emit(rc)
        except Exception as e:
            self.output_signal.emit(f"[EXECUTION ERROR]: {str(e)}")
            self.finished_signal.emit(-1)

class ADBFastbootGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Android Device Management v2.0")
        self.resize(900, 750)

        self.init_ui()

        # ADDITION: Automatically check for adb/fastboot upon app launch
        self.check_sdk_on_startup()

        self.refresh_devices()  # Automatically scan for devices when opening the app

    def check_sdk_on_startup(self):
        """ADDENDUM: Check whether `adb`/`fastboot` are already present in the OS or the `bin` directory."""
        has_adb = shutil.which("adb") is not None
        has_fastboot = shutil.which("fastboot") is not None

        if not (has_adb and has_fastboot):
            reply = QMessageBox.warning(
                self,
                "Missing dependencies",
                "The application couldn't find requirements dependencies installed in the system environment!\n\n"
                "Do you want to download and automatically set up the dependencies right now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.start_sdk_setup()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ------------------ TOP BAR: SETUP SDK & DEVICE SELECTOR ------------------
        top_group = QGroupBox("Environment and Device configuration")
        top_layout = QVBoxLayout(top_group)

        # Hàng 1: Nút Setup SDK tự động
        sdk_layout = QHBoxLayout()
        self.btn_setup_sdk = QPushButton("Setup Dependencies")
        self.btn_setup_sdk.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_setup_sdk.clicked.connect(self.start_sdk_setup)

        self.btn_doctor = QPushButton("Platform-Tools Doctor")
        self.btn_doctor.setStyleSheet("background-color: #16a085; color: white; font-weight: bold;")
        self.btn_doctor.clicked.connect(self.start_doctor)

        self.sdk_progress = QProgressBar()
        self.sdk_progress.setVisible(False)

        sdk_layout.addWidget(self.btn_setup_sdk)
        sdk_layout.addWidget(self.btn_doctor)
        sdk_layout.addWidget(self.sdk_progress)
        top_layout.addLayout(sdk_layout)

        # ------------------ KHU VỰC THIẾT BỊ (DEVICE SELECTOR) ------------------
        device_layout = QHBoxLayout()

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(250)
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)

        btn_refresh = QPushButton("Refresh devices list")
        btn_refresh.clicked.connect(self.refresh_devices)

        self.lbl_selected_device = QLabel("Scanning...")
        self.lbl_selected_device.setStyleSheet("font-weight: bold; color: #3498db;")

        device_layout.addWidget(QLabel("Select target device:"))
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(btn_refresh)
        device_layout.addStretch()
        device_layout.addWidget(self.lbl_selected_device)

        top_layout.addLayout(device_layout)
        main_layout.addWidget(top_group)

        # ------------------ TAB INTERFACE ------------------
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_adb_tab(), "ADB Management")
        self.tabs.addTab(self.create_fastboot_tab(), "Fastboot Operations")
        self.tabs.addTab(self.create_advanced_tab(), "ADB Sideload")
        main_layout.addWidget(self.tabs)

        # ------------------ CONSOLE LOG ------------------
        log_group = QGroupBox("Console output log")
        log_layout = QVBoxLayout(log_group)

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Courier New", 10))
        self.console_output.setStyleSheet("background-color: #1a1a1a; color: #2ecc71;")
        log_layout.addWidget(self.console_output)

        clear_btn = QPushButton("Delete logs")
        clear_btn.clicked.connect(self.console_output.clear)
        log_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

        main_layout.addWidget(log_group)

    def start_doctor(self):
        """Launch Thread Doctor"""
        self.btn_doctor.setEnabled(False)
        self.doctor_thread = SDKDoctorThread()
        self.doctor_thread.log_signal.connect(self.append_log)
        self.doctor_thread.finished_signal.connect(self.on_doctor_finished)
        self.doctor_thread.start()

    def on_doctor_finished(self, success: bool):
        self.btn_doctor.setEnabled(True)
        self.refresh_devices()

    def start_sdk_setup(self):
        """Launch the thread to load the SDK"""
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
            QMessageBox.information(self, "Success", "Successfully installed dependencies!")
            self.refresh_devices()
        else:
            QMessageBox.critical(self, "Error", "Unable to download dependencies. Please check your network connection!")

    def open_windows_driver_link(self):
        """Open the Google USB Driver download page if running on Windows"""
        if os.name == 'nt':
            import webbrowser
            webbrowser.open("https://developer.android.com/studio/run/win-usb")

    # ==================== FUNCTION TABS ====================

    def create_adb_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 1. Basic Operations
        basic_group = QGroupBox("Basic operations")
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

        # 2. File Management
        file_group = QGroupBox("Transferring Files and Directories")
        file_layout = QFormLayout(file_group)

        self.local_path_input = QLineEdit()
        btn_browse_local = QPushButton("Select File/Foler...")
        btn_browse_local.clicked.connect(self.browse_local_path)

        local_path_layout = QHBoxLayout()
        local_path_layout.addWidget(self.local_path_input)
        local_path_layout.addWidget(btn_browse_local)

        self.remote_path_input = QLineEdit()
        self.remote_path_input.setPlaceholderText("For example: /sdcard/Download/ or /data/local/tmp/")

        btn_push = QPushButton("Push to Device (Local -> Remote)")
        btn_push.setStyleSheet("background-color: #27ae60; color: white;")
        btn_push.clicked.connect(self.execute_push)

        btn_pull = QPushButton("Pull to Computer (Remote -> Local)")
        btn_pull.setStyleSheet("background-color: #2980b9; color: white;")
        btn_pull.clicked.connect(self.execute_pull)

        file_buttons = QHBoxLayout()
        file_buttons.addWidget(btn_push)
        file_buttons.addWidget(btn_pull)

        file_layout.addRow("Path on PC:", local_path_layout)
        file_layout.addRow("Path on Phone:", self.remote_path_input)
        file_layout.addRow("", file_buttons)
        layout.addWidget(file_group)

        # 3. Application Management
        app_group = QGroupBox("Application management (APK)")
        app_layout = QHBoxLayout(app_group)

        self.apk_input = QLineEdit()
        self.apk_input.setPlaceholderText("Select or drag and drop the .apk file path")
        btn_browse_apk = QPushButton("Browse APK file...")
        btn_browse_apk.clicked.connect(self.browse_apk_path)
        btn_install = QPushButton("Install APK")
        btn_install.setStyleSheet("font-weight: bold;")
        btn_install.clicked.connect(self.execute_install_apk)

        app_layout.addWidget(self.apk_input)
        app_layout.addWidget(btn_browse_apk)
        app_layout.addWidget(btn_install)
        layout.addWidget(app_group)

        # 4. Custom Shell Command
        shell_group = QGroupBox("Arbitrary shell command execution")
        shell_layout = QHBoxLayout(shell_group)
        self.shell_input = QLineEdit()
        self.shell_input.setPlaceholderText("Example: pm list packages | getprop ro.product.model")
        btn_shell = QPushButton("Run ADB shell")
        btn_shell.clicked.connect(self.execute_shell_command)

        shell_layout.addWidget(self.shell_input)
        shell_layout.addWidget(btn_shell)
        layout.addWidget(shell_group)

        layout.addStretch()
        return tab

    def create_fastboot_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        fb_basic_group = QGroupBox("General")
        fb_basic_layout = QHBoxLayout(fb_basic_group)

        btn_fb_devices = QPushButton("Device identification")
        btn_fb_devices.clicked.connect(lambda: self.run_fastboot_cmd(["devices"]))

        btn_getvar = QPushButton("View all information")
        btn_getvar.clicked.connect(lambda: self.run_fastboot_cmd(["getvar", "all"]))

        fb_basic_layout.addWidget(btn_fb_devices)
        fb_basic_layout.addWidget(btn_getvar)
        layout.addWidget(fb_basic_group)

        # 2. Addendum: Reboot Options
        reboot_group = QGroupBox("Restart mode")
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

        # 3. Addendum: Managing the Active Slot (A/B Partition)
        slot_group = QGroupBox("A/B slot management")
        slot_layout = QHBoxLayout(slot_group)

        btn_slot_a = QPushButton("Switch to slot A")
        btn_slot_a.clicked.connect(lambda: self.run_fastboot_cmd(["--set-active=a"]))

        btn_slot_b = QPushButton("Switch to slot B")
        btn_slot_b.clicked.connect(lambda: self.run_fastboot_cmd(["--set-active=b"]))

        slot_layout.addWidget(btn_slot_a)
        slot_layout.addWidget(btn_slot_b)
        layout.addWidget(slot_group)

        flash_group = QGroupBox("Flash partition")
        flash_layout = QFormLayout(flash_group)

        self.partition_input = QLineEdit()
        self.partition_input.setPlaceholderText("For example: boot, recovery, system, product, vendor...")

        self.img_path_input = QLineEdit()
        self.img_path_input.setPlaceholderText("Path to the .img file")
        btn_browse_img = QPushButton("Select Image File...")
        btn_browse_img.clicked.connect(self.browse_img_path)

        img_layout = QHBoxLayout()
        img_layout.addWidget(self.img_path_input)
        img_layout.addWidget(btn_browse_img)

        btn_flash = QPushButton("START FLASH")
        btn_flash.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        btn_flash.clicked.connect(self.execute_flash)

        flash_layout.addRow("Partition name:", self.partition_input)
        flash_layout.addRow("Image file (.img):", img_layout)
        flash_layout.addRow("", btn_flash)
        layout.addWidget(flash_group)

        layout.addStretch()
        return tab

    def run_fastboot_cmd(self, args: list[str]):
        """The helper invokes fastboot correctly, including the Device ID (-s) flag."""
        dev_id = self.get_selected_device_id()
        cmd = ["fastboot"]
        if dev_id:
            cmd.extend(["-s", dev_id])
        cmd.extend(args)
        self.run_cmd(cmd)

    def create_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        sideload_group = QGroupBox("ADB Sideload")
        sideload_layout = QFormLayout(sideload_group)

        self.ota_zip_input = QLineEdit()
        self.ota_zip_input.setPlaceholderText("Select the OTA zip file (.zip)")
        btn_browse_zip = QPushButton("Select ZIP file...")
        btn_browse_zip.clicked.connect(self.browse_zip_path)

        zip_layout = QHBoxLayout()
        zip_layout.addWidget(self.ota_zip_input)
        zip_layout.addWidget(btn_browse_zip)

        btn_reboot_sideload = QPushButton("Put the device into Sideload Mode")
        btn_reboot_sideload.clicked.connect(lambda: self.run_adb_cmd(["reboot", "sideload"]))

        btn_sideload = QPushButton("START SIDELOAD")
        btn_sideload.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold;")
        btn_sideload.clicked.connect(self.execute_sideload)

        sideload_layout.addRow("ZIP file:", zip_layout)
        sideload_layout.addRow(btn_reboot_sideload)
        sideload_layout.addRow(btn_sideload)

        layout.addWidget(sideload_group)
        layout.addStretch()
        return tab

    # ==================== FILE DIALOG BROWSERS ====================

    def browse_local_path(self):
        """Allows you to select files or folders on your PC properly, no scams."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("What would you like to do?")
        msg_box.setText("Do you want to select a FILE or a FOLDER?")

        btn_file = msg_box.addButton("Select File", QMessageBox.ButtonRole.YesRole)
        btn_folder = msg_box.addButton("Select Folder", QMessageBox.ButtonRole.NoRole)
        msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        clicked = msg_box.clickedButton()
        selected_path = ""

        if clicked == btn_file:
            file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
            selected_path = file_path
        elif clicked == btn_folder:
            folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
            selected_path = folder_path

        # Verify that the path is valid before assigning it to the QLineEdit.
        if selected_path:
            self.local_path_input.setText(selected_path)

    def browse_apk_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Android application file", "", "APK files (*.apk)")
        if file_path:
            self.apk_input.setText(file_path)

    def browse_img_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select image partition", "", "Image files (*.img *.bin)")
        if file_path:
            self.img_path_input.setText(file_path)

    def browse_zip_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select the compressed file for the upgrade", "", "ZIP files (*.zip)")
        if file_path:
            self.ota_zip_input.setText(file_path)

    # ==================== COORDINATION AND COMMAND EXECUTION ====================

    def refresh_devices(self):
        """Scan for both ADB and Fastboot devices"""
        self.device_combo.clear()
        found_devices = []

        # 1. ADB scan
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
            self.device_combo.addItem("No devices found")
            self.lbl_selected_device.setText("No Device")

    def on_device_selected(self, index):
        selected_id = self.device_combo.itemData(index)
        if selected_id:
            self.lbl_selected_device.setText(f"Active: {selected_id}")
        else:
            self.lbl_selected_device.setText("Waiting for device...")

    def get_selected_device_id(self) -> str:
        """Get the selected device ID from the QComboBox"""
        return self.device_combo.itemData(self.device_combo.currentIndex())

    def run_adb_cmd(self, command_args: list[str]):
        """Wrap ADB commands with the device-specific `-s` option"""
        dev_id = self.get_selected_device_id()
        if not dev_id:
            self.show_warn("No device selected for running the command!")
            return

        # Add the prefix 'adb -s <id>'
        full_command = ["adb", "-s", dev_id] + command_args
        self.run_cmd(full_command)

    def run_cmd(self, command: list[str]):
        """Spawn a sub-thread to execute a command"""
        # 1. Rename to self.cmd_thread to avoid conflict with the thread() method of QObject
        if hasattr(self, 'cmd_thread') and self.cmd_thread is not None and self.cmd_thread.isRunning():
            self.show_warn("A process is running in the background! Please wait for it to complete")
            return

        # Auto-kill fastboot bị dính kẹt USB Endpoint trên Linux
        if "fastboot" in command[0]:
            try:
                # Kill fastboot kẹt nếu chạy trên Linux/macOS
                if os.name != 'nt':
                    subprocess.run(["killall", "-q", "-9", "fastboot"], timeout=2)
                    subprocess.run(["killall", "-q", "-9", "adbd"], timeout=2)
                    subprocess.run(["killall", "-q", "-9", "adb"], timeout=2)
                else:
                    # Trên Windows dùng taskkill nếu cần
                    subprocess.run(["taskkill", "/F", "/IM", "fastboot.exe"], capture_output=True)
                    subprocess.run(["taskkill", "/F", "/IM", "adbd.exe"], capture_output=True)
                    subprocess.run(["taskkill", "/F", "/IM", "adb.exe"], capture_output=True)
            except Exception:
                pass

        cmd_str = " ".join(command)
        self.console_output.append(f"\n[RUNNING]: {cmd_str}\n" + "-" * 50)

        self.cmd_thread = CommandThread(command)
        self.cmd_thread.output_signal.connect(self.append_log)
        self.cmd_thread.finished_signal.connect(
            lambda code: self.append_log(f"\n[EXIT CODE]: {code}\n" + "=" * 50)
        )
        self.cmd_thread.start()

    def append_log(self, text: str):
        self.console_output.append(text)

    def show_warn(self, msg: str):
        QMessageBox.warning(self, "Notification", msg)

    # ==================== EXECUTE LOGIC ====================

    def execute_push(self):
        local = self.local_path_input.text().strip()
        remote = self.remote_path_input.text().strip()
        if not local or not remote:
            self.show_warn("Please enter the full local and remote paths!")
            return
        self.run_adb_cmd(["push", local, remote])

    def execute_pull(self):
        local = self.local_path_input.text().strip()
        remote = self.remote_path_input.text().strip()
        if not local or not remote:
            self.show_warn("Please enter the full local and remote paths!")
            return
        self.run_adb_cmd(["pull", remote, local])

    def execute_install_apk(self):
        apk = self.apk_input.text().strip()
        if not apk:
            self.show_warn("You have not selected the APK file to install!")
            return
        self.run_adb_cmd(["install", "-r", "-d", apk])

    def execute_shell_command(self):
        cmd = self.shell_input.text().strip()
        if not cmd:
            self.show_warn("Enter the shell command you wish to execute!")
            return
        self.run_adb_cmd(["shell", cmd])

    def execute_flash(self):
        part = self.partition_input.text().strip()
        img = self.img_path_input.text().strip()
        if not part or not img:
            self.show_warn("Insufficient partition information or Flash Image file provided!")
            return
        self.run_fastboot_cmd(["flash", part, img])

    def execute_sideload(self):
        zip_file = self.ota_zip_input.text().strip()
        if not zip_file:
            self.show_warn("Please select the .zip file you want to sideload first!")
            return
        # ADB Sideload command
        self.run_adb_cmd(["sideload", zip_file])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ADBFastbootGUI()
    window.show()
    exit_code = app.exec()
    # Dọn dẹp an toàn khi thoát App
    print("Application exit. Cleaning resources...")
    try:
        # Kill fastboot kẹt nếu chạy trên Linux/macOS
        if os.name != 'nt':
            subprocess.run(["killall", "-q", "-9", "fastboot"], timeout=2)
            subprocess.run(["killall", "-q", "-9", "adbd"], timeout=2)
            subprocess.run(["killall", "-q", "-9", "adb"], timeout=2)
        else:
            # Trên Windows dùng taskkill nếu cần
            subprocess.run(["taskkill", "/F", "/IM", "fastboot.exe"], capture_output=True)
            subprocess.run(["taskkill", "/F", "/IM", "adbd.exe"], capture_output=True)
            subprocess.run(["taskkill", "/F", "/IM", "adb.exe"], capture_output=True)
    except Exception:
        pass

    sys.exit(exit_code)
