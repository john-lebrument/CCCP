import ctypes
import time
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication

from app.storage import StorageManager

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


def force_window_foreground(hwnd: int) -> None:
    """Forcefully restore foreground and focus to target window across processes/threads."""
    if not hwnd or not user32.IsWindow(hwnd):
        return

    # Restore if minimized
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE

    cur_thread = kernel32.GetCurrentThreadId()
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)

    attached = False
    try:
        if cur_thread != target_thread and target_thread != 0:
            attached = bool(user32.AttachThreadInput(cur_thread, target_thread, True))

        user32.AllowSetForegroundWindow(-1)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        user32.SetActiveWindow(hwnd)
    except Exception:
        pass
    finally:
        if attached:
            user32.AttachThreadInput(cur_thread, target_thread, False)


def release_all_modifiers() -> None:
    """Ensure Alt, Ctrl, Shift, Win keys are logically released in Windows state."""
    modifier_vks = [
        0x12, 0xA4, 0xA5,  # Alt, LAlt, RAlt
        0x11, 0xA2, 0xA3,  # Ctrl, LCtrl, RCtrl
        0x10, 0xA0, 0xA1,  # Shift, LShift, RShift
        0x5B, 0x5C        # LWin, RWin
    ]
    for vk in modifier_vks:
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


class ClipboardManager(QObject):
    history_updated = pyqtSignal(dict)  # Emitted when a new history item is added

    def __init__(self, storage: StorageManager):
        super().__init__()
        self.storage = storage
        self.last_text = ""
        self._ignore_changes = False

        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self._on_clipboard_changed)

        # Initialize with current clipboard content if any
        current = self.clipboard.text()
        if current and current.strip():
            self.last_text = current
            self.storage.add_history(current)

    def _on_clipboard_changed(self) -> None:
        if self._ignore_changes:
            return

        try:
            text = self.clipboard.text()
        except Exception:
            return

        if not text or not text.strip():
            return

        if text != self.last_text:
            self.last_text = text
            added = self.storage.add_history(text)
            if added and self.storage.history:
                self.history_updated.emit(self.storage.history[0])

    def paste_text(self, text: str, target_hwnd: Optional[int] = None, add_to_history: bool = False) -> None:
        """Paste the provided text into the active/target window via Ctrl+V."""
        if not text:
            return

        # 1. First ensure all modifiers (Alt, Ctrl, Shift, Win) are released
        release_all_modifiers()

        # 2. Restore target window focus with thread input attachment
        if target_hwnd and user32.IsWindow(target_hwnd):
            force_window_foreground(target_hwnd)
            # Give sufficient time for Electron/Chromium/chat inputs to refocus text caret
            time.sleep(0.09)

        # Avoid registering our own paste into clipboard history unless explicitly wanted
        if not add_to_history:
            self._ignore_changes = True

        try:
            self.clipboard.setText(text)
            self.last_text = text

            # Give a moment for Windows clipboard to register the new text
            time.sleep(0.05)

            # Re-ensure modifiers are clean just before Ctrl+V
            release_all_modifiers()
            time.sleep(0.02)

            # Send Ctrl + V
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(VK_V, 0, 0, 0)
            time.sleep(0.03)
            user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.02)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

        finally:
            if not add_to_history:
                # Re-enable listening after a short delay
                QTimer.singleShot(300, self._enable_monitoring)

    def _enable_monitoring(self) -> None:
        self._ignore_changes = False
