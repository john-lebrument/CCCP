from typing import Callable
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt

from app.config import APP_TITLE, ICON_ICO, ICON_PNG


def create_default_icon() -> QIcon:
    """Load application icon from file if available, otherwise draw dynamically."""
    if ICON_ICO.exists():
        return QIcon(str(ICON_ICO))
    if ICON_PNG.exists():
        return QIcon(str(ICON_PNG))

    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Blue rounded badge
    p.setBrush(QColor("#0078d4"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)

    # Clipboard symbol
    p.setPen(QColor("white"))
    font = QFont("Segoe UI Emoji", 26, QFont.Weight.Bold)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "📋")
    p.end()

    return QIcon(pix)


class SystemTray(QSystemTrayIcon):
    def __init__(
        self,
        on_show_main: Callable[[], None],
        on_clear_history: Callable[[], None],
        on_quit_app: Callable[[], None],
        parent=None
    ):
        self.icon = create_default_icon()
        super().__init__(self.icon, parent)

        self.on_show_main = on_show_main
        self.on_clear_history = on_clear_history
        self.on_quit_app = on_quit_app

        self.setToolTip(APP_TITLE)
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #222222;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
        """)

        action_open = menu.addAction("⚡ Ouvrir SmartClipboard")
        action_open.triggered.connect(self.on_show_main)

        action_clear = menu.addAction("🧹 Vider l'historique")
        action_clear.triggered.connect(self.on_clear_history)

        menu.addSeparator()

        action_quit = menu.addAction("❌ Quitter l'application")
        action_quit.triggered.connect(self.on_quit_app)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.on_show_main()
