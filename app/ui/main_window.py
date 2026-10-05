import os
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit,
    QMessageBox, QFileDialog, QSpinBox, QCheckBox, QGroupBox, QSplitter,
    QDialog, QRadioButton, QButtonGroup, QMenu, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QAction

from app.config import (
    APP_TITLE, APP_VERSION, DATA_FILE, DEFAULT_MAX_HISTORY,
    DEFAULT_TRIGGER_MOUSE, DEFAULT_TRIGGER_HOTKEY
)
from app.storage import StorageManager
from app.clipboard_manager import ClipboardManager
from app.win_hooks import WindowsHookManager
from app.ui.snippet_dialog import SnippetEditDialog
from app.ui.shortcuts_dialog import ShortcutsViewerDialog
from app.ui.shortcut_input_widget import ShortcutInputWidget


class ReorderableTreeWidget(QTreeWidget):
    """QTreeWidget supporting internal drag & drop reordering of snippets and folders."""
    order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.order_changed.emit()


class MainWindow(QMainWindow):
    hotkeys_changed = pyqtSignal()

    def __init__(
        self,
        storage: StorageManager,
        clipboard_manager: ClipboardManager,
        hook_manager: WindowsHookManager
    ):
        super().__init__()
        self.storage = storage
        self.clipboard_manager = clipboard_manager
        self.hook_manager = hook_manager

        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.resize(850, 600)
        self.setMinimumSize(700, 480)

        # Connect signals
        self.clipboard_manager.history_updated.connect(self._on_history_updated)

        self._build_ui()
        self._refresh_snippets_tree()
        self._refresh_history_table()

    def _build_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Snippets / Arborescence
        self.tab_snippets = QWidget()
        self._setup_snippets_tab()
        self.tabs.addTab(self.tab_snippets, "📁 Extraits & Arborescence")

        # Tab 2: Clipboard History
        self.tab_history = QWidget()
        self._setup_history_tab()
        self.tabs.addTab(self.tab_history, "📋 Historique Presse-papier")

        # Tab 3: Settings & Backup
        self.tab_settings = QWidget()
        self._setup_settings_tab()
        self.tabs.addTab(self.tab_settings, "⚙️ Paramètres & Sauvegarde")

    # =========================================================================
    # TAB 1: SNIPPETS & TREE
    # =========================================================================
    def _setup_snippets_tab(self):
        layout = QVBoxLayout(self.tab_snippets)

        # Top Info Bar
        info_label = QLabel(
            "💡 <i>Maintenez <b>Alt + Clic Droit</b> dans n'importe quelle application pour ouvrir cette arborescence et coller votre texte.<br>"
            "Glissez-déposez les extraits pour réorganiser l'ordre ou les changer de dossier.</i>"
        )
        info_label.setStyleSheet("background-color: #f0f4f8; padding: 6px 10px; border-radius: 4px; border: 1px solid #d0d7de;")
        layout.addWidget(info_label)

        # Tree Widget with Drag & Drop Reordering
        self.tree = ReorderableTreeWidget()
        self.tree.setHeaderLabels(["Nom / Dossier", "Raccourci", "Aperçu"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(0, 300)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_clicked)
        self.tree.order_changed.connect(self._on_tree_reordered)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        layout.addWidget(self.tree, stretch=1)

        # Bottom Buttons
        btn_layout = QHBoxLayout()

        btn_add_folder = QPushButton("📁 Nouveau Dossier")
        btn_add_folder.clicked.connect(self._add_folder)

        btn_add_snippet = QPushButton("📄 Nouvel Extrait")
        btn_add_snippet.clicked.connect(self._add_snippet)

        self.btn_toggle_expand = QPushButton("🔽 Tout replier")
        self.btn_toggle_expand.setToolTip("Replier ou déplier l'ensemble des dossiers de l'arborescence en un clic")
        self.btn_toggle_expand.clicked.connect(self._toggle_tree_expand)
        self._tree_is_expanded = True

        btn_pin = QPushButton("📌 Épingler")
        btn_pin.clicked.connect(self._toggle_pin_selected_item)

        btn_edit = QPushButton("✏️ Modifier")
        btn_edit.clicked.connect(self._edit_selected_tree_item)

        btn_delete = QPushButton("🗑️ Supprimer")
        btn_delete.clicked.connect(self._delete_selected_tree_item)

        btn_copy = QPushButton("📋 Copier le texte")
        btn_copy.clicked.connect(self._copy_selected_snippet)

        btn_layout.addWidget(btn_add_folder)
        btn_layout.addWidget(btn_add_snippet)
        btn_layout.addWidget(self.btn_toggle_expand)
        btn_layout.addWidget(btn_pin)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_copy)

        layout.addLayout(btn_layout)

    def _toggle_tree_expand(self):
        if getattr(self, "_tree_is_expanded", True):
            self.tree.collapseAll()
            self._tree_is_expanded = False
            self.btn_toggle_expand.setText("▶️ Tout déplier")
        else:
            self.tree.expandAll()
            self._tree_is_expanded = True
            self.btn_toggle_expand.setText("🔽 Tout replier")

    def _refresh_snippets_tree(self):
        self.tree.clear()

        def _populate(parent_item, nodes):
            for node in nodes:
                node_type = node.get("type", "snippet")
                name = node.get("name", "")
                shortcut = node.get("shortcut", "")
                pinned = bool(node.get("pinned", False))
                content = node.get("content", "").replace("\n", " ").strip()
                if len(content) > 50:
                    content = content[:47] + "..."

                item = QTreeWidgetItem()
                if node_type == "folder":
                    label = f"📁 {name}"
                else:
                    label = f"📌 {name}" if pinned else f"📄 {name}"

                item.setText(0, label)
                item.setText(1, shortcut if node_type == "snippet" else "")
                item.setText(2, content if node_type == "snippet" else "")
                item.setData(0, Qt.ItemDataRole.UserRole, node)

                if parent_item is None:
                    self.tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)

                if node_type == "folder":
                    item.setExpanded(True)
                    _populate(item, node.get("children", []))

        _populate(None, self.storage.snippets)
        self._tree_is_expanded = True
        if hasattr(self, "btn_toggle_expand"):
            self.btn_toggle_expand.setText("🔽 Tout replier")
        self._sync_hotkeys_to_hook()

    def _get_selected_node_and_parent(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return None, None
        item = selected_items[0]
        node = item.data(0, Qt.ItemDataRole.UserRole)
        parent_item = item.parent()
        parent_node = parent_item.data(0, Qt.ItemDataRole.UserRole) if parent_item else None
        return node, parent_node

    def _add_folder(self):
        selected_node, _ = self._get_selected_node_and_parent()
        parent_id = None
        if selected_node and selected_node.get("type") == "folder":
            parent_id = selected_node.get("id")

        dialog = SnippetEditDialog(self, is_folder=True)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.storage.add_folder(parent_id, data["name"])
            self._refresh_snippets_tree()

    def _add_snippet(self):
        selected_node, _ = self._get_selected_node_and_parent()
        parent_id = None
        if selected_node:
            if selected_node.get("type") == "folder":
                parent_id = selected_node.get("id")
            else:
                _, parent_node = self._get_selected_node_and_parent()
                if parent_node:
                    parent_id = parent_node.get("id")

        dialog = SnippetEditDialog(self, is_folder=False)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.storage.add_snippet(parent_id, data["name"], data["content"], data.get("shortcut", ""))
            self._refresh_snippets_tree()

    def _edit_selected_tree_item(self):
        selected_node, _ = self._get_selected_node_and_parent()
        if not selected_node:
            QMessageBox.information(self, "Sélection requise", "Veuillez sélectionner un élément à modifier.")
            return

        is_folder = selected_node.get("type") == "folder"
        dialog = SnippetEditDialog(self, is_folder=is_folder, initial_data=selected_node)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.storage.update_node(selected_node.get("id"), **data)
            self._refresh_snippets_tree()

    def _delete_selected_tree_item(self):
        selected_node, _ = self._get_selected_node_and_parent()
        if not selected_node:
            QMessageBox.information(self, "Sélection requise", "Veuillez sélectionner un élément à supprimer.")
            return

        name = selected_node.get("name", "")
        reply = QMessageBox.question(
            self,
            "Confirmation de suppression",
            f"Êtes-vous sûr de vouloir supprimer '{name}' ?\n(S'il s'agit d'un dossier, tout son contenu sera supprimé)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.storage.delete_node(selected_node.get("id"))
            self._refresh_snippets_tree()

    def _copy_selected_snippet(self):
        selected_node, _ = self._get_selected_node_and_parent()
        if not selected_node or selected_node.get("type") != "snippet":
            QMessageBox.information(self, "Sélection requise", "Veuillez sélectionner un extrait à copier.")
            return
        content = selected_node.get("content", "")
        self.clipboard_manager.clipboard.setText(content)
        QMessageBox.information(self, "Copié", f"L'extrait '{selected_node.get('name')}' a été copié dans le presse-papier !")

    def _on_tree_double_clicked(self, item, column):
        self._edit_selected_tree_item()

    def _toggle_pin_selected_item(self):
        selected_node, _ = self._get_selected_node_and_parent()
        if not selected_node or selected_node.get("type") != "snippet":
            QMessageBox.information(self, "Sélection requise", "Veuillez sélectionner un extrait à épingler ou désépingler.")
            return

        new_state = self.storage.toggle_pinned(selected_node.get("id"))
        self._refresh_snippets_tree()
        status_str = "épinglé (sera proposé en premier)" if new_state else "désépinglé"
        self.statusBar().showMessage(f"Extrait '{selected_node.get('name')}' {status_str}.", 3000) if hasattr(self, 'statusBar') else None

    def _show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if not node:
            return

        menu = QMenu(self)
        is_snippet = node.get("type") == "snippet"

        if is_snippet:
            is_pinned = node.get("pinned", False)
            pin_text = "📌 Désépingler" if is_pinned else "📌 Épingler (proposer en premier)"
            action_pin = menu.addAction(pin_text)
            action_pin.triggered.connect(self._toggle_pin_selected_item)
            menu.addSeparator()

            action_copy = menu.addAction("📋 Copier le texte")
            action_copy.triggered.connect(self._copy_selected_snippet)

        action_edit = menu.addAction("✏️ Modifier")
        action_edit.triggered.connect(self._edit_selected_tree_item)

        action_del = menu.addAction("🗑️ Supprimer")
        action_del.triggered.connect(self._delete_selected_tree_item)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _dump_tree_hierarchy(self) -> List[Dict[str, Any]]:
        def _dump_item(item: QTreeWidgetItem) -> Dict[str, Any]:
            node = dict(item.data(0, Qt.ItemDataRole.UserRole))
            if node.get("type") == "folder":
                children = []
                for i in range(item.childCount()):
                    children.append(_dump_item(item.child(i)))
                node["children"] = children
            return node

        result = []
        for i in range(self.tree.topLevelItemCount()):
            result.append(_dump_item(self.tree.topLevelItem(i)))
        return result

    def _on_tree_reordered(self):
        new_hierarchy = self._dump_tree_hierarchy()
        self.storage.set_snippets(new_hierarchy)
        self._sync_hotkeys_to_hook()

    def _sync_hotkeys_to_hook(self):
        """Send all assigned shortcuts and open trigger hotkey to WindowsHookManager."""
        shortcut_dict = {}
        if self.storage.settings.get("enable_shortcuts", True):
            for node in self.storage.get_snippets_with_shortcuts():
                sc = node.get("shortcut", "").strip()
                if sc:
                    shortcut_dict[node.get("id")] = sc
        trigger_hotkey = self.storage.settings.get("trigger_hotkey", "")
        self.hook_manager.update_hotkeys(shortcut_dict, trigger_hotkey=trigger_hotkey)

    # =========================================================================
    # TAB 2: CLIPBOARD HISTORY
    # =========================================================================
    def _setup_history_tab(self):
        layout = QVBoxLayout(self.tab_history)

        # Search Bar
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Rechercher :")
        self.hist_search_input = QLineEdit()
        self.hist_search_input.setPlaceholderText("Filtrer l'historique en temps réel...")
        self.hist_search_input.textChanged.connect(self._on_search_filter_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.hist_search_input)
        layout.addLayout(search_layout)

        # Splitter with Table and Preview
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.hist_table = QTableWidget()
        self.hist_table.setColumnCount(4)
        self.hist_table.setHorizontalHeaderLabels(["#", "Aperçu du texte", "Taille", "Date / Heure"])
        self.hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.hist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.hist_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.hist_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.hist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.hist_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.hist_table.itemSelectionChanged.connect(self._on_history_selection_changed)
        self.hist_table.itemDoubleClicked.connect(self._on_history_double_clicked)
        self.hist_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist_table.customContextMenuRequested.connect(self._show_history_table_context_menu)
        splitter.addWidget(self.hist_table)

        # Preview box
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 5, 0, 0)
        preview_label = QLabel("<b>Aperçu complet du texte sélectionné :</b>")
        self.hist_preview = QPlainTextEdit()
        self.hist_preview.setReadOnly(True)
        self.hist_preview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hist_preview.customContextMenuRequested.connect(self._show_history_preview_context_menu)
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.hist_preview)
        splitter.addWidget(preview_container)

        splitter.setSizes([300, 150])
        layout.addWidget(splitter, stretch=1)

        # Bottom Buttons
        h_btn_layout = QHBoxLayout()

        btn_copy_hist = QPushButton("📋 Copier")
        btn_copy_hist.clicked.connect(self._copy_selected_history)

        btn_save_as_snippet = QPushButton("⭐ Enregistrer comme Extrait")
        btn_save_as_snippet.clicked.connect(self._save_history_as_snippet)

        btn_del_hist = QPushButton("🗑️ Supprimer")
        btn_del_hist.clicked.connect(self._delete_selected_history)

        btn_clear_hist = QPushButton("🧹 Vider tout l'historique")
        btn_clear_hist.clicked.connect(self._clear_all_history)

        h_btn_layout.addWidget(btn_copy_hist)
        h_btn_layout.addWidget(btn_save_as_snippet)
        h_btn_layout.addWidget(btn_del_hist)
        h_btn_layout.addStretch()
        h_btn_layout.addWidget(btn_clear_hist)

        layout.addLayout(h_btn_layout)

    def _refresh_history_table(self):
        query = self.hist_search_input.text().strip().lower()
        items = self.storage.history
        if query:
            items = [it for it in items if query in it.get("content", "").lower()]

        self.hist_table.setRowCount(len(items))
        for row, item in enumerate(items):
            content = item.get("content", "").replace("\n", " ").replace("\r", "")
            if len(content) > 70:
                content = content[:67] + "..."

            col_num = QTableWidgetItem(str(row + 1))
            col_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_preview = QTableWidgetItem(content)
            col_preview.setData(Qt.ItemDataRole.UserRole, item)

            col_size = QTableWidgetItem(f"{item.get('length', 0)} car.")
            col_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            col_time = QTableWidgetItem(item.get("timestamp", ""))
            col_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.hist_table.setItem(row, 0, col_num)
            self.hist_table.setItem(row, 1, col_preview)
            self.hist_table.setItem(row, 2, col_size)
            self.hist_table.setItem(row, 3, col_time)

    def _on_search_filter_changed(self):
        self._refresh_history_table()

    def _on_history_selection_changed(self):
        selected_rows = self.hist_table.selectedItems()
        if not selected_rows:
            self.hist_preview.clear()
            return
        row = self.hist_table.currentRow()
        item_cell = self.hist_table.item(row, 1)
        if item_cell:
            data = item_cell.data(Qt.ItemDataRole.UserRole)
            if data:
                self.hist_preview.setPlainText(data.get("content", ""))

    def _on_history_double_clicked(self, item):
        self._copy_selected_history()

    def _get_selected_history_item(self) -> Optional[Dict[str, Any]]:
        row = self.hist_table.currentRow()
        if row < 0:
            return None
        cell = self.hist_table.item(row, 1)
        return cell.data(Qt.ItemDataRole.UserRole) if cell else None

    def _copy_selected_history(self):
        item = self._get_selected_history_item()
        if not item:
            QMessageBox.information(self, "Sélection requise", "Veuillez sélectionner un élément de l'historique.")
            return
        self.clipboard_manager.clipboard.setText(item.get("content", ""))
        QMessageBox.information(self, "Copié", "Texte copié dans le presse-papier !")

    def _save_history_as_snippet(self):
        item = self._get_selected_history_item()
        if not item:
            QMessageBox.information(self, "Sélection requise", "Veuillez sélectionner un élément de l'historique.")
            return

        content = item.get("content", "")
        # Suggest name from first 25 chars
        default_name = content.strip().split("\n")[0][:25].strip()

        dialog = SnippetEditDialog(self, is_folder=False, initial_data={"name": default_name, "content": content})
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.storage.add_snippet(None, data["name"], data["content"], data.get("shortcut", ""))
            self._refresh_snippets_tree()
            self.tabs.setCurrentIndex(0)
            QMessageBox.information(self, "Extrait créé", f"L'extrait '{data['name']}' a été ajouté à vos snippets !")

    def _deposit_snippet_to_folder(self, content: str, folder_id: Optional[str], folder_path: str):
        if not content or not content.strip():
            return
        lines = [l.strip() for l in content.strip().splitlines() if l.strip()]
        first_line = lines[0] if lines else "Extrait"
        name = first_line[:35] + ("..." if len(first_line) > 35 else "")

        self.storage.add_snippet(folder_id, name=name, content=content)
        self._refresh_snippets_tree()
        msg = f"Extrait '{name}' déposé dans '{folder_path}' !"
        if hasattr(self, "statusBar") and self.statusBar():
            self.statusBar().showMessage(f"✅ {msg}", 4000)
        else:
            QMessageBox.information(self, "Extrait déposé", msg)

    def _show_history_preview_context_menu(self, pos):
        text = self.hist_preview.toPlainText().strip()
        if not text:
            return

        menu = self.hist_preview.createStandardContextMenu()
        menu.addSeparator()

        menu_deposit = menu.addMenu("📁 Déposer dans un dossier...")
        folders = self.storage.get_all_folders_flat()
        for fid, fpath in folders:
            act = menu_deposit.addAction(f"📁 {fpath}")
            act.triggered.connect(lambda ch, f_id=fid, p_name=fpath, t=text: self._deposit_snippet_to_folder(t, f_id, p_name))

        act_custom = menu.addAction("⭐ Déposer et personnaliser (Titre, Raccourci)...")
        act_custom.triggered.connect(self._save_history_as_snippet)

        menu.exec(self.hist_preview.mapToGlobal(pos))

    def _show_history_table_context_menu(self, pos):
        item = self._get_selected_history_item()
        if not item:
            return
        text = item.get("content", "").strip()
        if not text:
            return

        menu = QMenu(self)
        act_copy = menu.addAction("📋 Copier")
        act_copy.triggered.connect(self._copy_selected_history)
        menu.addSeparator()

        menu_deposit = menu.addMenu("📁 Déposer dans un dossier...")
        folders = self.storage.get_all_folders_flat()
        for fid, fpath in folders:
            act = menu_deposit.addAction(f"📁 {fpath}")
            act.triggered.connect(lambda ch, f_id=fid, p_name=fpath, t=text: self._deposit_snippet_to_folder(t, f_id, p_name))

        act_custom = menu.addAction("⭐ Déposer et personnaliser (Titre, Raccourci)...")
        act_custom.triggered.connect(self._save_history_as_snippet)

        menu.addSeparator()
        act_del = menu.addAction("🗑️ Supprimer")
        act_del.triggered.connect(self._delete_selected_history)

        menu.exec(self.hist_table.viewport().mapToGlobal(pos))

    def _delete_selected_history(self):
        item = self._get_selected_history_item()
        if not item:
            return
        self.storage.remove_history_item(item.get("id"))
        self._refresh_history_table()
        self.hist_preview.clear()

    def _clear_all_history(self):
        if not self.storage.history:
            return
        reply = QMessageBox.question(
            self,
            "Vider l'historique",
            "Voulez-vous vraiment vider l'ensemble de l'historique du presse-papier ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.storage.clear_history()
            self._refresh_history_table()
            self.hist_preview.clear()

    def _on_history_updated(self, item: dict):
        self._refresh_history_table()

    # =========================================================================
    # TAB 3: SETTINGS & BACKUP
    # =========================================================================
    def _setup_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)
        layout.setSpacing(15)

        # Group: Clipboard History Settings
        grp_hist = QGroupBox("Paramètres de l'historique")
        grp_hist_layout = QVBoxLayout(grp_hist)

        h_layout = QHBoxLayout()
        h_label = QLabel("Nombre maximum d'éléments à conserver :")
        self.spin_max_history = QSpinBox()
        self.spin_max_history.setRange(10, 500)
        self.spin_max_history.setValue(int(self.storage.settings.get("max_history", DEFAULT_MAX_HISTORY)))
        self.spin_max_history.valueChanged.connect(self._on_max_history_changed)
        h_layout.addWidget(h_label)
        h_layout.addWidget(self.spin_max_history)
        h_layout.addStretch()
        grp_hist_layout.addLayout(h_layout)

        layout.addWidget(grp_hist)

        # Group: Triggers / Mouse & Keyboard
        grp_triggers = QGroupBox("Déclencheurs & Raccourcis")
        grp_trig_layout = QVBoxLayout(grp_triggers)
        grp_trig_layout.setSpacing(10)

        # 1. Déclencheur souris
        mouse_layout = QHBoxLayout()
        mouse_label = QLabel("Déclencheur Souris (Menu flottant) :")
        mouse_label.setStyleSheet("font-weight: bold;")
        self.combo_mouse = QComboBox()
        self.mouse_trigger_options = [
            ("Alt + Clic Droit (Par défaut)", "Alt+RightClick"),
            ("Ctrl + Clic Droit", "Ctrl+RightClick"),
            ("Shift + Clic Droit", "Shift+RightClick"),
            ("Clic Molette (Milieu)", "MiddleClick"),
            ("Alt + Clic Molette", "Alt+MiddleClick"),
            ("Bouton Précédent Souris (XButton1)", "XButton1"),
            ("Bouton Suivant Souris (XButton2)", "XButton2"),
            ("Désactivé (Aucun)", "None"),
        ]
        for label, val in self.mouse_trigger_options:
            self.combo_mouse.addItem(label, val)

        current_mouse = self.storage.settings.get("trigger_mouse", DEFAULT_TRIGGER_MOUSE)
        for i in range(self.combo_mouse.count()):
            if self.combo_mouse.itemData(i) == current_mouse:
                self.combo_mouse.setCurrentIndex(i)
                break
        self.combo_mouse.currentIndexChanged.connect(self._on_mouse_trigger_changed)
        mouse_layout.addWidget(mouse_label)
        mouse_layout.addWidget(self.combo_mouse, stretch=1)
        grp_trig_layout.addLayout(mouse_layout)

        # 2. Déclencheur clavier d'ouverture
        hotkey_layout = QHBoxLayout()
        hotkey_label = QLabel("Raccourci Clavier d'ouverture :")
        hotkey_label.setStyleSheet("font-weight: bold;")
        current_hotkey = self.storage.settings.get("trigger_hotkey", DEFAULT_TRIGGER_HOTKEY)
        self.trigger_hotkey_input = ShortcutInputWidget(self, initial_shortcut=current_hotkey)
        self.trigger_hotkey_input.shortcutChanged.connect(self._on_trigger_hotkey_changed)
        hotkey_layout.addWidget(hotkey_label)
        hotkey_layout.addWidget(self.trigger_hotkey_input, stretch=1)
        grp_trig_layout.addLayout(hotkey_layout)

        hotkey_hint = QLabel("💡 <i>Pressez ce raccourci global n'importe où sous Windows pour ouvrir le menu sous votre curseur (ex: Ctrl+Alt+V ou Win+Num0). Laissez vide si vous n'utilisez que la souris.</i>")
        hotkey_hint.setStyleSheet("color: #666; font-size: 11px;")
        grp_trig_layout.addWidget(hotkey_hint)

        # 3. Activation des raccourcis individuels vers les extraits
        self.chk_shortcuts = QCheckBox("Activer les raccourcis clavier globaux vers les extraits")
        self.chk_shortcuts.setChecked(self.storage.settings.get("enable_shortcuts", True))
        self.chk_shortcuts.toggled.connect(self._on_shortcuts_toggled)
        grp_trig_layout.addWidget(self.chk_shortcuts)

        btn_view_shortcuts = QPushButton("⌨️ Afficher tous les raccourcis configurés...")
        btn_view_shortcuts.setStyleSheet("font-weight: bold; margin-top: 4px; padding: 5px;")
        btn_view_shortcuts.clicked.connect(self._show_shortcuts_viewer)
        grp_trig_layout.addWidget(btn_view_shortcuts)

        layout.addWidget(grp_triggers)

        # Group: Backup & Export / Import
        grp_backup = QGroupBox("Sauvegarde, Exportation & Importation")
        grp_backup_layout = QVBoxLayout(grp_backup)

        path_label = QLabel(f"Fichier de sauvegarde automatique : <code>{DATA_FILE}</code>")
        path_label.setTextFormat(Qt.TextFormat.RichText)
        path_label.setStyleSheet("color: #444; margin-bottom: 8px;")
        grp_backup_layout.addWidget(path_label)

        btn_box = QHBoxLayout()
        btn_export = QPushButton("📤 Exporter la bibliothèque (JSON)...")
        btn_export.clicked.connect(self._export_library)

        btn_import = QPushButton("📥 Importer une bibliothèque (JSON)...")
        btn_import.clicked.connect(self._import_library)

        btn_box.addWidget(btn_export)
        btn_box.addWidget(btn_import)
        grp_backup_layout.addLayout(btn_box)

        # CopyQ Import Button
        btn_copyq = QPushButton("📋 Importer un export CopyQ (.cpq)...")
        btn_copyq.setStyleSheet("background-color: #e8f4fd; color: #005a9e; font-weight: bold; padding: 6px;")
        btn_copyq.clicked.connect(self._import_copyq)
        grp_backup_layout.addWidget(btn_copyq)

        layout.addWidget(grp_backup)

        layout.addStretch()

        # About / Guide
        about_label = QLabel(
            f"<b>{APP_TITLE} v{APP_VERSION}</b><br>"
            "Fermer cette fenêtre la minimise discrètement dans la barre des tâches (près de l'horloge)."
        )
        about_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(about_label)

    def _on_max_history_changed(self, val: int):
        self.storage.settings["max_history"] = val
        self.storage.save()

    def _on_mouse_trigger_changed(self, index: int):
        val = self.combo_mouse.itemData(index)
        self.storage.settings["trigger_mouse"] = val
        self.hook_manager.set_trigger_mouse(val)
        self.storage.save()

    def _on_trigger_hotkey_changed(self, sc: str):
        self.storage.settings["trigger_hotkey"] = sc
        self.storage.save()
        self._sync_hotkeys_to_hook()

    def _on_shortcuts_toggled(self, checked: bool):
        self.storage.settings["enable_shortcuts"] = checked
        self._sync_hotkeys_to_hook()
        self.storage.save()

    def _show_shortcuts_viewer(self):
        dlg = ShortcutsViewerDialog(self.storage, self)
        dlg.shortcuts_updated.connect(self._refresh_snippets_tree)
        dlg.exec()

    def _export_library(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter la bibliothèque SmartClipboard",
            "SmartClipboard_Backup.json",
            "Fichier JSON (*.json)"
        )
        if path:
            success = self.storage.export_data(path, include_history=True)
            if success:
                QMessageBox.information(self, "Exportation réussie", f"Bibliothèque exportée avec succès dans :\n{path}")
            else:
                QMessageBox.critical(self, "Erreur", "Une erreur est survenue lors de l'exportation.")

    def _import_library(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer une bibliothèque",
            "",
            "Fichier JSON (*.json)"
        )
        if not path:
            return

        reply = QMessageBox.question(
            self,
            "Option d'importation",
            "Souhaitez-vous FUSIONNER avec vos snippets actuels ?\n\n"
            "- Cliquez sur 'Oui' pour fusionner (ajoute les nouveaux snippets sans effacer les vôtres).\n"
            "- Cliquez sur 'Non' pour remplacer complètement votre bibliothèque actuelle.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return

        merge = (reply == QMessageBox.StandardButton.Yes)
        success = self.storage.import_data(path, merge=merge)
        if success:
            self._refresh_snippets_tree()
            self._refresh_history_table()
            QMessageBox.information(self, "Importation terminée", "La bibliothèque a été importée avec succès !")
        else:
            QMessageBox.critical(self, "Erreur", "Impossible d'importer ce fichier. Vérifiez son format.")

    def _import_copyq(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier export CopyQ",
            "",
            "Export CopyQ (*.cpq);;Tous les fichiers (*.*)"
        )
        if not path:
            return

        reply = QMessageBox.question(
            self,
            "Option d'importation CopyQ",
            "Souhaitez-vous FUSIONNER les données CopyQ avec vos snippets actuels ?\n\n"
            "- Cliquez sur 'Oui' pour fusionner (ajoute les dossiers et historiques CopyQ).\n"
            "- Cliquez sur 'Non' pour remplacer complètement vos snippets actuels.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return

        merge = (reply == QMessageBox.StandardButton.Yes)
        try:
            stats = self.storage.import_copyq_data(path, merge=merge)
            self._refresh_snippets_tree()
            self._refresh_history_table()
            self.spin_max_history.setValue(int(self.storage.settings.get("max_history", DEFAULT_MAX_HISTORY)))
            QMessageBox.information(
                self,
                "Importation CopyQ réussie",
                f"Données CopyQ importées avec succès !\n\n"
                f"📁 Dossiers importés : {stats['folders']}\n"
                f"📄 Extraits (snippets) : {stats['snippets']}\n"
                f"📋 Éléments d'historique : {stats['history']}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erreur CopyQ", f"Erreur lors de l'importation du fichier CopyQ :\n{e}")

    # =========================================================================
    # WINDOW CLOSE BEHAVIOR
    # =========================================================================
    def closeEvent(self, event):
        """Minimize to system tray on close instead of exiting."""
        event.ignore()
        self.hide()
