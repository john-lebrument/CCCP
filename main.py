import sys
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

from app.config import APP_NAME, APP_TITLE
from app.storage import StorageManager
from app.clipboard_manager import ClipboardManager
from app.win_hooks import WindowsHookManager
from app.ui.main_window import MainWindow
from app.ui.popup_menu import SnippetPopupMenu
from app.ui.tray_icon import SystemTray, create_default_icon


def main():
    # Windows AppUserModelID for proper taskbar icon and notifications
    try:
        myappid = "smartclipboard.snippets.manager.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)

    app_icon = create_default_icon()
    app.setWindowIcon(app_icon)

    # Core managers
    storage = StorageManager()
    clipboard_mgr = ClipboardManager(storage)
    trigger_mouse = storage.settings.get("trigger_mouse", "Alt+RightClick")
    hook_mgr = WindowsHookManager(trigger_mouse=trigger_mouse)

    # Paste handlers
    def handle_paste(text: str, target_hwnd=None):
        clipboard_mgr.paste_text(text, target_hwnd=target_hwnd)

    def handle_open_manager():
        window.show()
        window.raise_()
        window.activateWindow()

    # UI Windows & Tray
    window = MainWindow(storage, clipboard_mgr, hook_mgr)
    window.setWindowIcon(app_icon)

    # Popup menu for Alt + Right Click
    popup = SnippetPopupMenu(
        storage=storage,
        on_select_paste=handle_paste,
        on_open_manager=handle_open_manager,
        on_data_changed=window._refresh_snippets_tree
    )

    def handle_quit():
        hook_mgr.stop()
        app.quit()

    def handle_clear_history():
        storage.clear_history()
        window._refresh_history_table()

    tray = SystemTray(
        on_show_main=handle_open_manager,
        on_clear_history=handle_clear_history,
        on_quit_app=handle_quit
    )
    tray.show()

    # Hook signals
    def on_alt_right_click(x: int, y: int, target_hwnd: int):
        QTimer.singleShot(15, lambda: popup.show_at(x, y, target_hwnd))

    def on_hotkey(snippet_id: str):
        # Look for snippet in flat list
        for node, _ in storage.get_all_snippets_flat():
            if node.get("id") == snippet_id:
                content = node.get("content", "")
                if content:
                    storage.bump_snippet(snippet_id)
                    window._refresh_snippets_tree()
                    handle_paste(content)
                break

    hook_mgr.signals.alt_right_click_triggered.connect(on_alt_right_click)
    hook_mgr.signals.hotkey_triggered.connect(on_hotkey)

    # Start low-level hook thread
    hook_mgr.start()

    # Initial sync of hotkeys
    window._sync_hotkeys_to_hook()

    # Show main window on first launch
    window.show()

    try:
        sys.exit(app.exec())
    finally:
        hook_mgr.stop()


if __name__ == "__main__":
    main()
