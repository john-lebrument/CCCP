import ctypes
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QAction

user32 = ctypes.windll.user32


class ShortcutCaptureLineEdit(QLineEdit):
    """Champ de saisie capable de capturer les raccourcis au clavier incluant Win et Pavé numérique."""
    shortcutChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Ex: Win+Num1 ou Ctrl+Alt+A")
        self.is_recording = False

    def start_recording(self):
        self.is_recording = True
        self.setStyleSheet("border: 2px solid #e74c3c; background-color: #fffafa;")
        self.setPlaceholderText("Pressez vos touches... (Echap pour annuler)")
        self.setFocus()

    def stop_recording(self):
        self.is_recording = False
        self.setStyleSheet("")
        self.setPlaceholderText("Ex: Win+Num1 ou Ctrl+Alt+A")

    def focusOutEvent(self, event):
        if self.is_recording:
            self.stop_recording()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if not self.is_recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        vk = event.nativeVirtualKey()
        mods = event.modifiers()

        # Ne pas valider si uniquement une touche modificatrice
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            event.accept()
            return

        if key == Qt.Key.Key_Escape:
            self.stop_recording()
            event.accept()
            return

        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.setText("")
            self.stop_recording()
            self.shortcutChanged.emit("")
            event.accept()
            return

        parts = []

        # Détection touche Windows
        is_win = bool(mods & Qt.KeyboardModifier.MetaModifier)
        if not is_win:
            try:
                is_win = bool(
                    (user32.GetAsyncKeyState(0x5B) & 0x8000) or  # VK_LWIN
                    (user32.GetAsyncKeyState(0x5C) & 0x8000)     # VK_RWIN
                )
            except Exception:
                pass

        if is_win:
            parts.append("Win")
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")

        # Résolution de la touche principale
        key_str = ""
        # Pavé numérique VK (0x60 à 0x69)
        if 0x60 <= vk <= 0x69:
            key_str = f"Num{vk - 0x60}"
        elif vk == 0x6A:
            key_str = "Num*"
        elif vk == 0x6B:
            key_str = "Num+"
        elif vk == 0x6D:
            key_str = "Num-"
        elif vk == 0x6E:
            key_str = "Num."
        elif vk == 0x6F:
            key_str = "Num/"
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            key_str = f"F{key - Qt.Key.Key_F1 + 1}"
        elif 0x30 <= vk <= 0x39:  # Chiffres réguliers
            key_str = chr(vk)
        elif 0x41 <= vk <= 0x5A:  # Lettres A-Z
            key_str = chr(vk)
        else:
            text = event.text().upper().strip()
            if text and len(text) == 1 and text.isprintable():
                key_str = text
            else:
                name = Qt.Key(key).name
                if name.startswith("Key_"):
                    name = name[4:]
                key_str = name

        if key_str:
            parts.append(key_str)
            final_str = "+".join(parts)
            self.setText(final_str)
            self.stop_recording()
            self.shortcutChanged.emit(final_str)
            event.accept()
        else:
            super().keyPressEvent(event)


class ShortcutInputWidget(QWidget):
    """Composant complet avec saisie, capture et menu d'aide pour le pavé numérique."""
    shortcutChanged = pyqtSignal(str)

    def __init__(self, parent=None, initial_shortcut: str = ""):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.line_edit = ShortcutCaptureLineEdit(self)
        self.line_edit.setText(initial_shortcut)
        self.line_edit.shortcutChanged.connect(self.shortcutChanged.emit)
        self.line_edit.textChanged.connect(self.shortcutChanged.emit)
        layout.addWidget(self.line_edit, stretch=1)

        self.btn_record = QPushButton("🔴 Enregistrer")
        self.btn_record.setToolTip("Cliquer puis presser votre combinaison de touches")
        self.btn_record.clicked.connect(self._toggle_record)
        layout.addWidget(self.btn_record)

        self.btn_presets = QPushButton("⚡ Pavé Num ▾")
        self.btn_presets.setToolTip("Choisir rapidement un raccourci Win + Pavé Numérique ou Ctrl+Alt")
        self._setup_presets_menu()
        layout.addWidget(self.btn_presets)

        self.btn_clear = QPushButton("Effacer")
        self.btn_clear.clicked.connect(self.clear)
        layout.addWidget(self.btn_clear)

    def _toggle_record(self):
        if self.line_edit.is_recording:
            self.line_edit.stop_recording()
            self.btn_record.setText("🔴 Enregistrer")
        else:
            self.line_edit.start_recording()
            self.btn_record.setText("⏹️ Annuler")

    def _setup_presets_menu(self):
        menu = QMenu(self)

        # Win + Num
        menu_win = menu.addMenu("Touche Windows (Win + Num...)")
        for i in range(10):
            sc = f"Win+Num{i}"
            act = menu_win.addAction(sc)
            act.triggered.connect(lambda ch, s=sc: self.set_shortcut(s))

        menu.addSeparator()

        # Ctrl + Alt + Num
        menu_ctrl_alt = menu.addMenu("Ctrl + Alt + Num...")
        for i in range(10):
            sc = f"Ctrl+Alt+Num{i}"
            act = menu_ctrl_alt.addAction(sc)
            act.triggered.connect(lambda ch, s=sc: self.set_shortcut(s))

        # Ctrl + Num
        menu_ctrl = menu.addMenu("Ctrl + Num...")
        for i in range(10):
            sc = f"Ctrl+Num{i}"
            act = menu_ctrl.addAction(sc)
            act.triggered.connect(lambda ch, s=sc: self.set_shortcut(s))

        # Alt + Num
        menu_alt = menu.addMenu("Alt + Num...")
        for i in range(10):
            sc = f"Alt+Num{i}"
            act = menu_alt.addAction(sc)
            act.triggered.connect(lambda ch, s=sc: self.set_shortcut(s))

        self.btn_presets.setMenu(menu)

    def set_shortcut(self, shortcut: str):
        self.line_edit.setText(shortcut)
        self.shortcutChanged.emit(shortcut)

    def get_shortcut(self) -> str:
        return self.line_edit.text().strip()

    def clear(self):
        self.line_edit.setText("")
        self.shortcutChanged.emit("")
