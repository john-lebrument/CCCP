from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QDialogButtonBox, QMessageBox,
    QCheckBox
)
from PyQt6.QtCore import Qt

from app.ui.shortcut_input_widget import ShortcutInputWidget


class SnippetEditDialog(QDialog):
    def __init__(self, parent=None, is_folder: bool = False, initial_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.is_folder = is_folder
        self.initial_data = initial_data or {}

        title = "Dossier" if is_folder else "Extrait (Snippet)"
        action = "Modifier" if initial_data else "Nouveau"
        self.setWindowTitle(f"{action} {title}")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Name / Title
        name_label = QLabel("Nom du dossier :" if self.is_folder else "Titre de l'extrait :")
        name_label.setStyleSheet("font-weight: bold;")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex: Salutations" if self.is_folder else "Ex: Reste à disposition")
        layout.addWidget(name_label)
        layout.addWidget(self.name_input)

        if not self.is_folder:
            # Content
            content_label = QLabel("Contenu du texte à coller :")
            content_label.setStyleSheet("font-weight: bold;")
            self.content_input = QPlainTextEdit()
            self.content_input.setPlaceholderText("Saisissez le texte complet ici...")
            self.content_input.setMinimumHeight(120)
            layout.addWidget(content_label)
            layout.addWidget(self.content_input)

            # Shortcut
            shortcut_label = QLabel("Raccourci clavier (optionnel) :")
            shortcut_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(shortcut_label)

            self.shortcut_input = ShortcutInputWidget(self)
            layout.addWidget(self.shortcut_input)

            hint = QLabel("💡 <i>Cliquez sur '🔴 Enregistrer' puis pressez vos touches, ou utilisez le menu '⚡ Pavé Num' pour choisir un raccourci Win + Pavé numérique.</i>")
            hint.setStyleSheet("color: #666; font-size: 11px;")
            layout.addWidget(hint)

            # Pinned Checkbox
            self.pinned_checkbox = QCheckBox("📌 Épingler cet extrait (proposé en premier)")
            self.pinned_checkbox.setStyleSheet("font-weight: bold; margin-top: 6px;")
            layout.addWidget(self.pinned_checkbox)

        # Buttons OK / Annuler
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_data(self):
        if self.initial_data:
            self.name_input.setText(self.initial_data.get("name", ""))
            if not self.is_folder:
                self.content_input.setPlainText(self.initial_data.get("content", ""))
                sc = self.initial_data.get("shortcut", "")
                self.shortcut_input.set_shortcut(sc)
                self.pinned_checkbox.setChecked(bool(self.initial_data.get("pinned", False)))

    def _validate_and_accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Champ manquant", "Veuillez indiquer un nom.")
            self.name_input.setFocus()
            return

        if not self.is_folder:
            content = self.content_input.toPlainText()
            if not content.strip():
                QMessageBox.warning(self, "Champ manquant", "Veuillez saisir un contenu pour cet extrait.")
                self.content_input.setFocus()
                return

        self.accept()

    def get_data(self) -> Dict[str, Any]:
        data = {
            "name": self.name_input.text().strip(),
        }
        if not self.is_folder:
            data["content"] = self.content_input.toPlainText()
            data["shortcut"] = self.shortcut_input.get_shortcut()
            data["pinned"] = self.pinned_checkbox.isChecked()
        return data
