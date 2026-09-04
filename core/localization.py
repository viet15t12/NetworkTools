"""Persistent UI language selection and notification-focused translations."""

from __future__ import annotations

import re
from collections.abc import Callable

from PyQt6.QtCore import QObject, QSettings, pyqtProperty, pyqtSignal, pyqtSlot


_VIETNAMESE_TEXT: dict[str, str] = {
    # Language/settings surfaces.
    "Language": "Ngôn ngữ",
    "English": "English",
    "Vietnamese": "Tiếng Việt",
    "Interface language": "Ngôn ngữ giao diện",
    "Choose the language used by CAMS.": "Chọn ngôn ngữ được CAMS sử dụng.",
    "The language choice is saved automatically and notification messages are translated first.":
        "Lựa chọn ngôn ngữ được tự động lưu và các dòng thông báo được ưu tiên dịch trước.",
    "Technical terms such as host, SSH, Telnet, VLAN, OSPF, workspace, database, and CLI remain unchanged.":
        "Các thuật ngữ kỹ thuật như host, SSH, Telnet, VLAN, OSPF, workspace, database và CLI được giữ nguyên.",
    "Settings": "Cài đặt",
    "SETTINGS": "CÀI ĐẶT",
    "Search settings...": "Tìm cài đặt...",
    "No matching settings group.": "Không có nhóm cài đặt phù hợp.",
    "Theme": "Giao diện",
    "Theme, accent, and Status Bar settings": "Theme, màu nhấn và cài đặt Status Bar",
    "External Tools": "External Tools",
    "Open External Tools": "Mở External Tools",
    "Choose default, suggested, or custom applications": "Chọn ứng dụng mặc định, được đề xuất hoặc tùy chỉnh",
    "Default local and remote connection directories": "Thư mục kết nối local và remote mặc định",
    "System Logs": "System Logs",
    "Listener, device destination, and message retention": "Listener, đích thiết bị và thời gian lưu message",
    "Language and notification translation": "Ngôn ngữ và bản dịch thông báo",
    "Global Settings": "Cài đặt chung",
    "Appearance is available before a project is opened": "Có thể chỉnh giao diện trước khi mở project",
    "Color theme": "Color theme",
    "System": "Hệ thống",
    "Light": "Sáng",
    "Dark": "Tối",
    "High contrast": "Độ tương phản cao",
    "Additional global settings remain available from the workspace Settings view.":
        "Các cài đặt chung khác vẫn có trong mục Settings của workspace.",
    "Done": "Xong",
    "Welcome": "Chào mừng",
    "Choose a project to continue": "Chọn project để tiếp tục",
    "Create New": "Tạo mới",
    "Start a new .ntp workspace": "Bắt đầu một workspace .ntp mới",
    "Open": "Mở",
    "Open a CAMS project": "Mở một project CAMS",
    "Configure global appearance": "Cấu hình giao diện chung",
    "Notifications": "Thông báo",
    "No New Notifications": "Không có thông báo mới",
    "Clear All Notifications": "Xóa tất cả thông báo",
    "Do Not Disturb - ON": "Không làm phiền - BẬT",
    "Do Not Disturb - ON (click to turn OFF)": "Không làm phiền - BẬT (bấm để TẮT)",
    "Do Not Disturb - OFF (click to turn ON)": "Không làm phiền - TẮT (bấm để BẬT)",
    "Create Project": "Tạo project",
    "Open Project": "Mở project",
    "Unlock Project": "Mở khóa project",
    "Project password": "Mật khẩu project",
    "Enter the project password": "Nhập mật khẩu project",
    "CAMS does not store project passwords.": "CAMS không lưu mật khẩu project.",
    "Cancel": "Hủy",
    "Unlock": "Mở khóa",

    # High-frequency notifications and task states. Technical terms stay intact.
    "Task completed.": "Task đã hoàn tất.",
    "Task failed.": "Task thất bại.",
    "Python runtime is ready.": "Python runtime đã sẵn sàng.",
    "Select a device before opening CLI.": "Hãy chọn thiết bị trước khi mở CLI.",
    "Select a device before opening CAMS Terminal.":
        "Hãy chọn thiết bị trước khi mở CAMS Terminal.",
    "CAMS Terminal backend is not available.": "CAMS Terminal backend hiện không khả dụng.",
    "Device is waiting. Configuration is disabled.": "Thiết bị đang chờ. Configuration đang bị vô hiệu hóa.",
    "Device added in waiting state. Configuration is disabled until connected.":
        "Đã thêm thiết bị ở trạng thái chờ. Configuration bị vô hiệu hóa cho đến khi kết nối.",
    "Host is empty.": "Host đang trống.",
    "Ping failed: host is empty.": "Ping thất bại: host đang trống.",
    "Connect failed: host is empty.": "Kết nối thất bại: host đang trống.",
    "Open session failed: host is empty.": "Mở session thất bại: host đang trống.",
    "Command failed: host is empty.": "Command thất bại: host đang trống.",
    "Command failed: command is empty.": "Command thất bại: command đang trống.",
    "Get running-config failed: host is empty.": "Lấy running-config thất bại: host đang trống.",
    "Save configuration failed: host is empty.": "Lưu configuration thất bại: host đang trống.",
    "Manual Sync failed: host is empty.": "Manual Sync thất bại: host đang trống.",
    "Manual Sync apply request is invalid.": "Yêu cầu apply Manual Sync không hợp lệ.",
    "No configuration required for Push.": "Không có configuration cần Push.",
    "Push completed.": "Push đã hoàn tất.",
    "Push failed.": "Push thất bại.",
    "DHCP push completed.": "Push DHCP đã hoàn tất.",
    "NAT push completed.": "Push NAT đã hoàn tất.",
    "ACL push completed.": "Push ACL đã hoàn tất.",
    "DHCP push finished with errors.": "Push DHCP hoàn tất nhưng có lỗi.",
    "NAT push finished with errors.": "Push NAT hoàn tất nhưng có lỗi.",
    "ACL push finished with errors.": "Push ACL hoàn tất nhưng có lỗi.",
    "Worker succeeded, but no DHCP database rows were updated.":
        "Worker thành công nhưng không có row nào trong database DHCP được cập nhật.",
    "Unsaved changes": "Có thay đổi chưa lưu",
    "Saved": "Đã lưu",
    "Save failed": "Lưu thất bại",
    "Save conflict": "Xung đột khi lưu",
    "Auto-saving workspace…": "Đang tự động lưu workspace…",
    "Saving workspace…": "Đang lưu workspace…",
    "Creating snapshot…": "Đang tạo snapshot…",
    "Rolling back workspace…": "Đang rollback workspace…",
    "Disconnecting devices and packing workspace…": "Đang ngắt kết nối thiết bị và đóng gói workspace…",
    "Workspace saved.": "Đã lưu workspace.",
    "Workspace auto-saved.": "Workspace đã được tự động lưu.",
    "Snapshot created and workspace saved.": "Đã tạo snapshot và lưu workspace.",
    "Workspace rolled back and saved.": "Đã rollback và lưu workspace.",
    "Choose a local folder.": "Hãy chọn thư mục local.",
    "Choose an existing folder.": "Hãy chọn thư mục đang tồn tại.",
    "Choose an existing project folder.": "Hãy chọn thư mục project đang tồn tại.",
    "Choose a local project path.": "Hãy chọn đường dẫn project local.",
    "Choose a project path.": "Hãy chọn đường dẫn project.",
    "Choose a local .ntp file.": "Hãy chọn file .ntp local.",
    "Choose a project file.": "Hãy chọn file project.",
    "Close the active workspace before creating another project.":
        "Hãy đóng workspace hiện tại trước khi tạo project khác.",
    "Close the active workspace before opening another project.":
        "Hãy đóng workspace hiện tại trước khi mở project khác.",
    "This project is password protected.": "Project này được bảo vệ bằng mật khẩu.",
    "The password is incorrect or the project was modified.":
        "Mật khẩu không đúng hoặc project đã bị thay đổi.",
}


def _rule(pattern: str, replacement: str) -> tuple[re.Pattern[str], str]:
    return re.compile(pattern), replacement


_VIETNAMESE_PATTERNS: tuple[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]], ...] = (
    _rule(r"^Connecting to (.+)\.\.\.$", r"Đang kết nối tới \1..."),
    _rule(r"^Opening device connection to (.+)\.\.\.$", r"Đang mở kết nối thiết bị tới \1..."),
    _rule(r"^Finished connection task for (.+)\.$", r"Đã hoàn tất task kết nối cho \1."),
    _rule(r"^Opening CLI session to (.+)\.\.\.$", r"Đang mở CLI session tới \1..."),
    _rule(r"^CAMS (Terminal|CLI) is ready for (.+)\.$", r"CAMS \1 đã sẵn sàng cho \2."),
    _rule(r"^CAMS (Terminal|CLI) opened for (.+)\.$", r"Đã mở CAMS \1 cho \2."),
    _rule(r"^CAMS (Terminal|CLI) failed for (.+)\.$", r"CAMS \1 thất bại cho \2."),
    _rule(r"^Failed to open CAMS Terminal for (.+)\.$", r"Không thể mở CAMS Terminal cho \1."),
    _rule(r"^Command completed for (.+)\.$", r"Command đã hoàn tất trên \1."),
    _rule(r"^Command failed for (.+): (.+)$", r"Command thất bại trên \1: \2"),
    _rule(r"^Waiting for device response from (.+)\.\.\.$", r"Đang chờ phản hồi thiết bị từ \1..."),
    _rule(r"^Getting running-config from (.+)\.\.\.$", r"Đang lấy running-config từ \1..."),
    _rule(r"^Collecting complete running-config from (.+)\.\.\.$", r"Đang thu thập đầy đủ running-config từ \1..."),
    _rule(r"^Saving configuration on (.+)\.\.\.$", r"Đang lưu configuration trên \1..."),
    _rule(r"^Manual Sync started for (.+)\.\.\.$", r"Đã bắt đầu Manual Sync cho \1..."),
    _rule(r"^Manual Sync finished for (.+)\.$", r"Manual Sync đã hoàn tất cho \1."),
    _rule(r"^Started (\d+) connect task\(s\)\.$", r"Đã bắt đầu \1 task kết nối."),
    _rule(r"^Started bounded connect batch for (\d+) host\(s\)\.$", r"Đã bắt đầu batch kết nối giới hạn cho \1 host."),
    _rule(r"^Prepared (\d+) (.+) task\(s\)\.$", r"Đã chuẩn bị \1 task \2."),
    _rule(r"^(DHCP|NAT|ACL) push finished with errors: (.+)$", r"Push \1 hoàn tất nhưng có lỗi: \2"),
    _rule(r"^Push (.+) failed for (.+)\.$", r"Push \1 thất bại trên \2."),
    _rule(r"^Push (.+) failed: (.+)$", r"Push \1 thất bại: \2"),
    _rule(r"^Background synchronization completed for (.+)\.$", r"Background synchronization đã hoàn tất cho \1."),
    _rule(r"^Background synchronization failed for (.+): (.+)$", r"Background synchronization thất bại cho \1: \2"),
    _rule(r"^Device (.+) was not found\.$", r"Không tìm thấy thiết bị \1."),
    _rule(r"^Missing Python packages: (.+)$", r"Thiếu Python package: \1"),
    _rule(r"^(\d+) Unread Notifications$", r"\1 thông báo chưa đọc"),
    _rule(r"^Do Not Disturb - ON \((\d+) unread\)$", r"Không làm phiền - BẬT (\1 chưa đọc)"),
)


class LanguageSettings(QObject):
    """Expose a saved English/Vietnamese choice and safe UI-boundary translation."""

    languageChanged = pyqtSignal()
    SUPPORTED_LANGUAGES = {"en", "vi"}

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings if settings is not None else QSettings()
        self._language = self._normalize_language(
            self._settings.value("Language/code", "en")
        )

    @classmethod
    def _normalize_language(cls, value: object) -> str:
        normalized = str(value or "").strip().casefold()
        return normalized if normalized in cls.SUPPORTED_LANGUAGES else "en"

    @pyqtProperty(str, notify=languageChanged)
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, value: str) -> None:
        normalized = self._normalize_language(value)
        if normalized == self._language:
            return
        self._language = normalized
        self._settings.setValue("Language/code", normalized)
        self._settings.sync()
        self.languageChanged.emit()

    @pyqtProperty(bool, notify=languageChanged)
    def isVietnamese(self) -> bool:
        return self._language == "vi"

    @pyqtSlot(str)
    def setLanguage(self, value: str) -> None:
        self.language = value

    @pyqtSlot(str, result=str)
    def translate(self, source: str) -> str:
        text = str(source or "")
        if self._language != "vi" or not text:
            return text
        translated = _VIETNAMESE_TEXT.get(text)
        if translated is not None:
            return translated
        for pattern, replacement in _VIETNAMESE_PATTERNS:
            if pattern.fullmatch(text):
                return pattern.sub(replacement, text)
        return text


__all__ = ["LanguageSettings"]
