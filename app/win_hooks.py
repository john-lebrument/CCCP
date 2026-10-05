import ctypes
from ctypes import wintypes
import threading
import queue
from typing import Dict, Tuple, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_MOUSE_LL = 14
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_HOTKEY = 0x0312
WM_USER = 0x0400
WM_UPDATE_HOTKEYS = WM_USER + 1
WM_STOP_THREAD = WM_USER + 2

OPEN_MENU_HOTKEY_ID = 99999

VK_MENU = 0x12
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_CONTROL = 0x11
VK_SHIFT = 0x10

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]


user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_longlong
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL


def parse_shortcut(shortcut_str: str) -> Optional[Tuple[int, int]]:
    """Parse a string like 'Ctrl+Alt+D' or 'Win+Num1' into (modifiers, vk_code)."""
    if not shortcut_str or not shortcut_str.strip():
        return None

    parts = [p.strip().upper() for p in shortcut_str.split("+")]
    if not parts:
        return None

    modifiers = 0
    key_part = parts[-1]

    for p in parts[:-1]:
        if p in ("CTRL", "CONTROL"):
            modifiers |= MOD_CONTROL
        elif p == "ALT":
            modifiers |= MOD_ALT
        elif p == "SHIFT":
            modifiers |= MOD_SHIFT
        elif p in ("WIN", "WINDOWS", "META", "SUPER"):
            modifiers |= MOD_WIN

    # Key resolution
    vk = 0

    # 1. Numpad check
    for prefix in ("NUMPAD", "NUM", "KP_", "PAVÉ", "PAVE"):
        if key_part.startswith(prefix):
            suffix = key_part[len(prefix):]
            if suffix.isdigit() and len(suffix) == 1:
                vk = 0x60 + int(suffix)
                break
            elif suffix in ("+", "ADD"):
                vk = 0x6B
                break
            elif suffix in ("-", "SUB", "SUBTRACT"):
                vk = 0x6D
                break
            elif suffix in ("*", "MUL", "MULTIPLY"):
                vk = 0x6A
                break
            elif suffix in ("/", "DIV", "DIVIDE"):
                vk = 0x6F
                break
            elif suffix in (".", ",", "DECIMAL"):
                vk = 0x6E
                break

    if vk == 0:
        if len(key_part) == 1:
            vk = ord(key_part)
        elif key_part.startswith("F") and key_part[1:].isdigit():
            f_num = int(key_part[1:])
            if 1 <= f_num <= 24:
                vk = 0x70 + (f_num - 1)
        else:
            key_map = {
                "ENTER": 0x0D,
                "RETURN": 0x0D,
                "SPACE": 0x20,
                "ESPACE": 0x20,
                "TAB": 0x09,
                "ESCAPE": 0x1B,
                "ESC": 0x1B,
                "INSERT": 0x2D,
                "DELETE": 0x2E,
                "SUPPR": 0x2E,
                "HOME": 0x24,
                "DEBUT": 0x24,
                "END": 0x23,
                "FIN": 0x23,
                "PAGEUP": 0x21,
                "PGUP": 0x21,
                "PAGEDOWN": 0x22,
                "PGDOWN": 0x22,
            }
            vk = key_map.get(key_part, 0)
            if not vk:
                vk = user32.VkKeyScanW(ord(key_part[0])) & 0xFF

    if vk == 0:
        return None

    return modifiers | MOD_NOREPEAT, vk


class WindowsHookSignals(QObject):
    alt_right_click_triggered = pyqtSignal(int, int, int)  # x, y, target_hwnd
    hotkey_triggered = pyqtSignal(str)  # snippet_id


class WindowsHookManager:
    """Manages configurable mouse hook and Windows global hotkeys in a dedicated thread."""

    def __init__(self, trigger_mouse: str = "Alt+RightClick"):
        self.signals = WindowsHookSignals()
        self.thread: Optional[threading.Thread] = None
        self.thread_id: Optional[int] = None
        self.hook_handle: Optional[int] = None
        self.c_hook_proc: Optional[HOOKPROC] = None

        # Hotkeys: hotkey_int_id -> (snippet_id, mod, vk)
        self.registered_hotkeys: Dict[int, str] = {}
        self.pending_hotkeys_queue = queue.Queue()
        self.enabled_alt_right_click = True
        self.trigger_mouse = trigger_mouse
        self.trigger_hotkey = ""
        self._swallow_up_msg = None

        self._started_event = threading.Event()

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return

        self._started_event.clear()
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        self._started_event.wait(timeout=2.0)

    def stop(self) -> None:
        if self.thread_id and user32.IsWindow(0):
            pass
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_STOP_THREAD, 0, 0)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None
        self.thread_id = None

    def update_hotkeys(self, snippet_shortcuts: Dict[str, str], trigger_hotkey: str = "") -> None:
        """Pass a dict of snippet_id -> shortcut_str, and optional trigger_hotkey."""
        self.trigger_hotkey = trigger_hotkey
        self.pending_hotkeys_queue.put((snippet_shortcuts, trigger_hotkey))
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_UPDATE_HOTKEYS, 0, 0)

    def set_trigger_mouse(self, trigger_mouse: str) -> None:
        self.trigger_mouse = trigger_mouse

    def _mouse_hook_proc(self, nCode: int, wParam: wintypes.WPARAM, lParam: wintypes.LPARAM) -> int:
        if nCode >= 0:
            # Swallow mouse up if matching previous triggered mouse down
            if self._swallow_up_msg is not None and wParam == self._swallow_up_msg:
                self._swallow_up_msg = None
                return 1

            if self.enabled_alt_right_click and self.trigger_mouse != "None":
                is_alt_pressed = (
                    (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
                    or (user32.GetAsyncKeyState(VK_LMENU) & 0x8000) != 0
                    or (user32.GetAsyncKeyState(VK_RMENU) & 0x8000) != 0
                )
                is_ctrl_pressed = (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0
                is_shift_pressed = (user32.GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0

                triggered = False
                tm = self.trigger_mouse

                if tm == "Alt+RightClick" and wParam == WM_RBUTTONDOWN and is_alt_pressed:
                    triggered = True
                    self._swallow_up_msg = WM_RBUTTONUP
                elif tm == "Ctrl+RightClick" and wParam == WM_RBUTTONDOWN and is_ctrl_pressed:
                    triggered = True
                    self._swallow_up_msg = WM_RBUTTONUP
                elif tm == "Shift+RightClick" and wParam == WM_RBUTTONDOWN and is_shift_pressed:
                    triggered = True
                    self._swallow_up_msg = WM_RBUTTONUP
                elif tm == "MiddleClick" and wParam == WM_MBUTTONDOWN and not (is_alt_pressed or is_ctrl_pressed or is_shift_pressed):
                    triggered = True
                    self._swallow_up_msg = WM_MBUTTONUP
                elif tm == "Alt+MiddleClick" and wParam == WM_MBUTTONDOWN and is_alt_pressed:
                    triggered = True
                    self._swallow_up_msg = WM_MBUTTONUP
                elif tm.startswith("XButton") and wParam == WM_XBUTTONDOWN:
                    triggered = True
                    self._swallow_up_msg = WM_XBUTTONUP

                if triggered:
                    target_hwnd = user32.GetForegroundWindow()
                    mouse_info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    x = mouse_info.pt.x
                    y = mouse_info.pt.y

                    self.signals.alt_right_click_triggered.emit(x, y, target_hwnd)
                    return 1

        return user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)

    def _worker_loop(self) -> None:
        self.thread_id = kernel32.GetCurrentThreadId()

        # Install low-level mouse hook
        self.c_hook_proc = HOOKPROC(self._mouse_hook_proc)
        self.hook_handle = user32.SetWindowsHookExW(WH_MOUSE_LL, self.c_hook_proc, 0, 0)
        if not self.hook_handle:
            print(f"[WinHooks] Warning: Failed to install mouse hook. Error: {kernel32.GetLastError()}")

        self._started_event.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            if msg.message == WM_STOP_THREAD:
                break

            elif msg.message == WM_UPDATE_HOTKEYS:
                self._apply_pending_hotkeys()

            elif msg.message == WM_HOTKEY:
                hotkey_id = int(msg.wParam)
                if hotkey_id == OPEN_MENU_HOTKEY_ID:
                    pt = POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    target_hwnd = user32.GetForegroundWindow()
                    self.signals.alt_right_click_triggered.emit(pt.x, pt.y, target_hwnd)
                else:
                    snippet_id = self.registered_hotkeys.get(hotkey_id)
                    if snippet_id:
                        self.signals.hotkey_triggered.emit(snippet_id)

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        self._unregister_all_hotkeys()
        if self.hook_handle:
            user32.UnhookWindowsHookEx(self.hook_handle)
            self.hook_handle = None

    def _unregister_all_hotkeys(self) -> None:
        for hotkey_id in list(self.registered_hotkeys.keys()):
            user32.UnregisterHotKey(None, hotkey_id)
        self.registered_hotkeys.clear()
        user32.UnregisterHotKey(None, OPEN_MENU_HOTKEY_ID)

    def _apply_pending_hotkeys(self) -> None:
        latest_item = None
        while not self.pending_hotkeys_queue.empty():
            try:
                latest_item = self.pending_hotkeys_queue.get_nowait()
            except queue.Empty:
                break

        if latest_item is None:
            return

        latest_dict, trigger_hotkey = latest_item

        self._unregister_all_hotkeys()

        # 1. Register main open menu hotkey if configured
        if trigger_hotkey and trigger_hotkey.strip():
            parsed_open = parse_shortcut(trigger_hotkey.strip())
            if parsed_open:
                mod_open, vk_open = parsed_open
                succ = user32.RegisterHotKey(None, OPEN_MENU_HOTKEY_ID, mod_open, vk_open)
                if succ:
                    print(f"[WinHooks] Global open menu hotkey registered: {trigger_hotkey}")
                else:
                    print(f"[WinHooks] Failed to register open menu hotkey {trigger_hotkey} (err: {kernel32.GetLastError()})")

        # 2. Register snippet hotkeys
        current_id = 1
        for snippet_id, shortcut_str in latest_dict.items():
            parsed = parse_shortcut(shortcut_str)
            if parsed:
                modifiers, vk = parsed
                success = user32.RegisterHotKey(None, current_id, modifiers, vk)
                if success:
                    self.registered_hotkeys[current_id] = snippet_id
                    current_id += 1
                else:
                    print(f"[WinHooks] Failed to register hotkey {shortcut_str} for {snippet_id} (err: {kernel32.GetLastError()})")
