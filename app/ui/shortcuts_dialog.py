from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QDialogButtonBox, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.storage import StorageManager
from app.ui.snippet_dialog import SnippetEditDialog


class ShortcutsViewerDialog(QDialog):
    shortcuts_updated = pyqtSignal()

    def __init__(self, storage: StorageManager, parent=None):
        super().__init__(parent)
        self.storage = storage

        self.setWindowTitle("⌨️ Tous les Raccourcis Clavier Configurés")
        self.resize(750, 450)
        self.setMinimumSize(600, 350)

        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header Info
        info_label = QLabel(
            "Liste de tous les extraits associés à un raccourci clavier global. "
            "<i>Pressez ce raccourci n'importe où sous Windows pour coller immédiatement votre texte.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #444; font-size: 12px; margin-bottom: 4px;")
        layout.addWidget(info_label)

        # Search Bar
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Filtrer :")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher par raccourci, nom ou contenu...")
        self.search_input.textChanged.connect(self._refresh_table)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Suppr.", "Raccourci", "Nom de l'extrait", "Emplacement", "Aperçu du texte"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemDoubleClicked.connect(self._on_edit_clicked)
        layout.addWidget(self.table, stretch=1)

        # Bottom Buttons
        btn_layout = QHBoxLayout()

        btn_edit = QPushButton("✏️ Modifier le raccourci / l'extrait")
        btn_edit.clicked.connect(self._on_edit_clicked)

        btn_copy = QPushButton("📋 Copier le texte")
        btn_copy.clicked.connect(self._on_copy_clicked)

        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_copy)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

    def _get_items_with_shortcuts(self) -> List[Dict[str, Any]]:
        flat = self.storage.get_all_snippets_flat()
        items = []
        for node, path in flat:
            shortcut = node.get("shortcut", "").strip()
            if shortcut:
                # Path without snippet name
                parent_path = " > ".join(path.split(" > ")[:-1]) if " > " in path else "(Racine)"
                items.append({
                    "node": node,
                    "shortcut": shortcut,
                    "name": node.get("name", "Sans nom"),
                    "path": parent_path,
                    "content": node.get("content", ""),
                })
        return items

    def _refresh_table(self):
        query = self.search_input.text().strip().lower()
        items = self._get_items_with_shortcuts()

        if query:
            items = [
                it for it in items
                if query in it["shortcut"].lower()
                or query in it["name"].lower()
                or query in it["path"].lower()
                or query in it["content"].lower()
            ]

        self.table.setRowCount(len(items))

        bold_font = QFont()
        bold_font.setBold(True)

        for row, it in enumerate(items):
            # Column 0: Bouton rouge supprimer
            btn_del = QPushButton("❌")
            btn_del.setToolTip("Supprimer ce raccourci clavier")
            btn_del.setFixedSize(26, 24)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet("""
                QPushButton {
                    border: 1px solid #ffcccc;
                    background-color: #fff0f0;
                    border-radius: 4px;
                    color: #d9534f;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e74c3c;
                    color: white;
                }
            """)
            node_ref = it["node"]
            btn_del.clicked.connect(lambda ch, n=node_ref: self._on_delete_shortcut(n))

            container = QWidget()
            c_layout = QHBoxLayout(container)
            c_layout.setContentsMargins(2, 2, 2, 2)
            c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(btn_del)
            self.table.setCellWidget(row, 0, container)

            # Column 1: Shortcut text
            col_sc = QTableWidgetItem(f"  {it['shortcut']}  ")
            col_sc.setFont(bold_font)
            col_sc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            col_sc.setData(Qt.ItemDataRole.UserRole, it["node"])

            # Column 2: Name
            col_name = QTableWidgetItem(f"📄 {it['name']}")

            # Column 3: Path
            col_path = QTableWidgetItem(f"📁 {it['path']}")

            # Column 4: Preview
            preview = it["content"].replace("\n", " ").replace("\r", "").strip()
            if len(preview) > 60:
                preview = preview[:57] + "..."
            col_preview = QTableWidgetItem(preview)

            self.table.setItem(row, 1, col_sc)
            self.table.setItem(row, 2, col_name)
            self.table.setItem(row, 3, col_path)
            self.table.setItem(row, 4, col_preview)

    def _get_selected_node(self) -> Optional[Dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0:
            return None
        cell = self.table.item(row, 1)
        return cell.data(Qt.ItemDataRole.UserRole) if cell else None

    def _on_delete_shortcut(self, node: Dict[str, Any]):
        reply = QMessageBox.question(
            self,
            "Supprimer le raccourci",
            f"Voulez-vous supprimer le raccourci clavier '{node.get('shortcut')}' associé à '{node.get('name')}' ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.storage.update_node(node.get("id"), shortcut="")
            self._refresh_table()
            self.shortcuts_updated.emit()

    def _on_edit_clicked(self):
        node = self._get_selected_node()
        if not node:
            QMessageBox.information(self, "Sélection requise", "Veuillez sélectionner un extrait à modifier.")
            return

        dialog = SnippetEditDialog(self, is_folder=False, initial_data=node)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.storage.update_node(node.get("id"), **data)
            self._refresh_table()
            self.shortcuts_updated.emit()

    def _on_copy_clicked(self):
        node = self._get_selected_node()
        if not node:
            return
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(node.get("content", ""))
        QMessageBox.information(self, "Copié", f"Texte de '{node.get('name')}' copié dans le presse-papier !")
