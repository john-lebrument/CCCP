import ctypes
from typing import List, Dict, Any, Callable, Optional
from PyQt6.QtWidgets import (
    QMenu, QApplication, QWidget, QVBoxLayout, QLabel,
    QDialog, QMessageBox, QPlainTextEdit, QFrame
)
from PyQt6.QtGui import QAction, QIcon, QCursor, QFont, QMouseEvent, QKeyEvent
from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal, QEvent

from app.storage import StorageManager
from app.ui.snippet_dialog import SnippetEditDialog

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class SnippetPreviewPopup(QWidget):
    """Bulle flottante affichant l'intégralité du texte lors du survol d'un élément."""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #0078d4;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header info
        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet("font-weight: bold; color: #005a9e; font-size: 11px; border: none;")
        layout.addWidget(self.title_lbl)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("background-color: #e0e0e0; max-height: 1px; border: none;")
        layout.addWidget(sep)

        # Content preview (scrollable or clean multiline)
        self.content_lbl = QLabel()
        self.content_lbl.setWordWrap(True)
        self.content_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.content_lbl.setStyleSheet("""
            color: #222222;
            font-size: 12px;
            font-family: 'Segoe UI', sans-serif;
            line-height: 1.3;
            border: none;
            background: transparent;
        """)
        self.content_lbl.setMaximumWidth(450)
        self.content_lbl.setMaximumHeight(350)
        layout.addWidget(self.content_lbl)

    def show_preview(self, title: str, text: str, anchor_rect, screen_geometry):
        length = len(text)
        self.title_lbl.setText(f"{title}  ({length} caractères)")

        display_text = text if length <= 1500 else text[:1490] + "\n... [texte tronqué]"
        self.content_lbl.setText(display_text)
        self.adjustSize()

        # Position to the right of anchor_rect, or to the left if near screen edge
        popup_w = self.sizeHint().width()
        popup_h = self.sizeHint().height()

        target_x = anchor_rect.right() + 4
        if target_x + popup_w > screen_geometry.right():
            target_x = max(screen_geometry.left() + 5, anchor_rect.left() - popup_w - 4)

        target_y = anchor_rect.top()
        if target_y + popup_h > screen_geometry.bottom():
            target_y = max(screen_geometry.top() + 5, screen_geometry.bottom() - popup_h - 10)

        self.move(target_x, target_y)
        self.show()


class CustomPopupMenu(QMenu):
    """QMenu personnalisé avec gestion du clic droit et détection du survol prolongé."""
    action_right_clicked = pyqtSignal(QAction, QPoint)
    action_hover_changed = pyqtSignal(QAction, object)  # action, rect
    mouse_left_menu = pyqtSignal()

    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.installEventFilter(self)

    def addMenu(self, title: str) -> 'CustomPopupMenu':
        sub = CustomPopupMenu(title, self)
        sub.setStyleSheet(self.styleSheet())
        sub.action_right_clicked.connect(self.action_right_clicked.emit)
        sub.action_hover_changed.connect(self.action_hover_changed.emit)
        sub.mouse_left_menu.connect(self.mouse_left_menu.emit)
        super().addMenu(sub)
        return sub

    def eventFilter(self, obj, event):
        if obj == self:
            # 1. Ignorer le relâchement des touches modificatrices (ex: Alt, Win) pour éviter la fermeture involontaire
            if event.type() == QEvent.Type.KeyRelease:
                if event.key() in (Qt.Key.Key_Alt, Qt.Key.Key_AltGr, Qt.Key.Key_Meta, Qt.Key.Key_Control, Qt.Key.Key_Shift):
                    return True

            # 2. Intercepter le clic droit sur un élément du menu
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.RightButton:
                    action = self.actionAt(event.pos())
                    if action and action.isEnabled() and not action.isSeparator():
                        global_pos = self.mapToGlobal(event.pos())
                        self.action_right_clicked.emit(action, global_pos)
                        return True

            # 3. Détecter le survol précis pour le pop-up d'aperçu
            elif event.type() == QEvent.Type.MouseMove:
                action = self.actionAt(event.pos())
                if action and action.isEnabled() and not action.isSeparator():
                    action_rect = self.actionGeometry(action)
                    top_left = self.mapToGlobal(action_rect.topLeft())
                    bottom_right = self.mapToGlobal(action_rect.bottomRight())
                    from PyQt6.QtCore import QRect
                    global_rect = QRect(top_left, bottom_right)
                    self.action_hover_changed.emit(action, global_rect)

            elif event.type() == QEvent.Type.Leave:
                self.mouse_left_menu.emit()

        return super().eventFilter(obj, event)


class SnippetPopupMenu:
    """Gestionnaire du menu flottant hiérarchique pour extraits et historique avec aperçu au survol."""

    MENU_STYLESHEET = """
        QMenu {
            background-color: #ffffff;
            color: #222222;
            border: 1px solid #c0c0c0;
            border-radius: 6px;
            padding: 4px;
            font-size: 13px;
            font-family: 'Segoe UI', sans-serif;
        }
        QMenu::item {
            padding: 6px 24px 6px 12px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: #0078d4;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background-color: #e0e0e0;
            margin: 4px 8px;
        }
    """

    def __init__(
        self,
        storage: StorageManager,
        on_select_paste: Callable[[str, Optional[int]], None],
        on_open_manager: Callable[[], None],
        on_data_changed: Optional[Callable[[], None]] = None
    ):
        self.storage = storage
        self.on_select_paste = on_select_paste
        self.on_open_manager = on_open_manager
        self.on_data_changed = on_data_changed

        # Preview Popup
        self.preview_popup = SnippetPreviewPopup()

        # Hover timer for "une petite seconde" (~700ms)
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(700)
        self.hover_timer.timeout.connect(self._on_hover_timeout)

        self.pending_hover = None  # (title, content, global_rect)
        self.current_menu = None

    def _on_hover_timeout(self):
        if self.pending_hover and self.current_menu and self.current_menu.isVisible():
            title, content, global_rect = self.pending_hover
            screen = QApplication.primaryScreen()
            screen_geo = screen.availableGeometry() if screen else global_rect
            self.preview_popup.show_preview(title, content, global_rect, screen_geo)

    def _on_action_hover(self, action: QAction, global_rect):
        data = action.data()
        if data and isinstance(data, dict) and data.get("content"):
            title = data.get("title", "Aperçu")
            content = data.get("content", "")
            self.pending_hover = (title, content, global_rect)
            self.hover_timer.start(700)
        else:
            self.hover_timer.stop()
            self.preview_popup.hide()

    def _on_menu_leave(self):
        self.hover_timer.stop()
        self.preview_popup.hide()

    def show_at(self, x: int, y: int, target_hwnd: Optional[int] = None) -> None:
        # Force Windows foreground activation
        user32.AllowSetForegroundWindow(-1)

        menu = CustomPopupMenu()
        menu.setStyleSheet(self.MENU_STYLESHEET)
        self.current_menu = menu

        menu.action_hover_changed.connect(self._on_action_hover)
        menu.mouse_left_menu.connect(self._on_menu_leave)
        menu.action_right_clicked.connect(lambda act, pt: self._handle_right_click(act, pt, menu))

        # Title header
        title_action = menu.addAction("⚡ CCCP - Couper, Copier, Coller")
        title_action.setEnabled(False)
        menu.addSeparator()

        # 1. Extraits épinglés
        pinned_snippets = self.storage.get_pinned_snippets()
        if pinned_snippets:
            pin_title = menu.addAction("📌 ÉPINGLÉS (Prioritaires)")
            pin_title.setEnabled(False)
            for snip in pinned_snippets:
                name = snip.get("name", "Sans nom")
                shortcut = snip.get("shortcut", "")
                label = f"📌 {name}"
                if shortcut:
                    label += f"  [{shortcut}]"
                action = menu.addAction(label)
                action.setData({
                    "type": "snippet",
                    "node": snip,
                    "content": snip.get("content", ""),
                    "title": f"📌 {name}"
                })
                action.triggered.connect(
                    lambda checked=False, n=snip: self._handle_snippet_click(n, target_hwnd)
                )

            menu.addSeparator()

        # 2. Arborescence des extraits
        self._build_tree_menu(menu, self.storage.snippets, target_hwnd)

        menu.addSeparator()

        # 3. Historique récent
        hist_menu = menu.addMenu("📋 Historique récent")
        history = self.storage.history
        if not history:
            no_hist = hist_menu.addAction("Aucun historique")
            no_hist.setEnabled(False)
        else:
            for i, item in enumerate(history[:15]):
                content = item.get("content", "").strip()
                preview = content.replace("\n", " ").replace("\r", "")
                if len(preview) > 40:
                    preview = preview[:37] + "..."
                time_str = item.get("timestamp", "").split(" ")[-1] if " " in item.get("timestamp", "") else ""
                label = f"{i+1}. {preview}  ({time_str})" if time_str else f"{i+1}. {preview}"

                action = hist_menu.addAction(label)
                action.setData({
                    "type": "history",
                    "item": item,
                    "content": content,
                    "title": f"📋 Historique #{i+1}"
                })
                action.triggered.connect(
                    lambda checked=False, txt=content: self.on_select_paste(txt, target_hwnd)
                )

        menu.addSeparator()

        # Ouvrir le gestionnaire
        mgr_action = menu.addAction("⚙️ Ouvrir le gestionnaire CCCP...")
        mgr_action.triggered.connect(self.on_open_manager)

        # Position and display
        pos = QPoint(x, y)
        try:
            menu.exec(pos)
        finally:
            self.hover_timer.stop()
            self.preview_popup.hide()
            self.current_menu = None

    def _build_tree_menu(self, parent_menu: CustomPopupMenu, nodes: List[Dict[str, Any]], target_hwnd: Optional[int]) -> None:
        if not nodes:
            empty_action = parent_menu.addAction("(Vide)")
            empty_action.setEnabled(False)
            return

        for node in nodes:
            node_type = node.get("type", "snippet")
            name = node.get("name", "Sans nom")

            if node_type == "folder":
                sub_menu = parent_menu.addMenu(f"📁 {name}")
                self._build_tree_menu(sub_menu, node.get("children", []), target_hwnd)
            else:
                shortcut = node.get("shortcut", "")
                pinned = node.get("pinned", False)
                icon_prefix = "📌 " if pinned else "📄 "
                label = f"{icon_prefix}{name}"
                if shortcut:
                    label += f"  [{shortcut}]"

                action = parent_menu.addAction(label)
                action.setData({
                    "type": "snippet",
                    "node": node,
                    "content": node.get("content", ""),
                    "title": f"📄 {name}"
                })
                action.triggered.connect(
                    lambda checked=False, n=node: self._handle_snippet_click(n, target_hwnd)
                )

    def _handle_right_click(self, action: QAction, global_pos: QPoint, main_menu: CustomPopupMenu):
        """Affiche le menu contextuel du clic droit (Éditer / Supprimer)."""
        data = action.data()
        if not data or not isinstance(data, dict):
            return

        # Cacher l'aperçu avant d'afficher le menu contextuel
        self.hover_timer.stop()
        self.preview_popup.hide()

        ctx = QMenu()
        ctx.setStyleSheet(self.MENU_STYLESHEET)

        action_type = data.get("type")

        if action_type == "snippet":
            node = data.get("node", {})
            name = node.get("name", "Extrait")
            shortcut = node.get("shortcut", "").strip()

            header = ctx.addAction(f"📄 {name}")
            header.setEnabled(False)
            ctx.addSeparator()

            act_edit = ctx.addAction("✏️ Modifier le contenu / l'extrait...")

            act_del_sc = None
            if shortcut:
                act_del_sc = ctx.addAction(f"❌ Supprimer le raccourci [{shortcut}]")

            act_del_snippet = ctx.addAction("🗑️ Supprimer cet extrait")

            chosen = ctx.exec(global_pos)
            if not chosen:
                return

            main_menu.close()

            if chosen == act_edit:
                dlg = SnippetEditDialog(parent=None, is_folder=False, initial_data=node)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    new_data = dlg.get_data()
                    self.storage.update_node(node.get("id"), **new_data)
                    if self.on_data_changed:
                        self.on_data_changed()

            elif chosen == act_del_sc:
                self.storage.update_node(node.get("id"), shortcut="")
                if self.on_data_changed:
                    self.on_data_changed()

            elif chosen == act_del_snippet:
                reply = QMessageBox.question(
                    None,
                    "Supprimer l'extrait",
                    f"Voulez-vous vraiment supprimer définitivement l'extrait '{name}' ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.storage.delete_node(node.get("id"))
                    if self.on_data_changed:
                        self.on_data_changed()

        elif action_type == "history":
            item = data.get("item", {})
            content = item.get("content", "")

            header = ctx.addAction("📋 Élément Historique")
            header.setEnabled(False)
            ctx.addSeparator()

            act_save_as = ctx.addAction("⭐ Enregistrer comme Extrait et éditer...")
            act_del_hist = ctx.addAction("🗑️ Supprimer de l'historique")

            chosen = ctx.exec(global_pos)
            if not chosen:
                return

            main_menu.close()

            if chosen == act_save_as:
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                default_name = lines[0][:30].strip() if lines else "Extrait"
                dlg = SnippetEditDialog(
                    parent=None,
                    is_folder=False,
                    initial_data={"name": default_name, "content": content}
                )
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    new_data = dlg.get_data()
                    self.storage.add_snippet(
                        None,
                        name=new_data["name"],
                        content=new_data["content"],
                        shortcut=new_data.get("shortcut", ""),
                        pinned=new_data.get("pinned", False)
                    )
                    if self.on_data_changed:
                        self.on_data_changed()

            elif chosen == act_del_hist:
                self.storage.remove_history_item(item.get("id"))
                if self.on_data_changed:
                    self.on_data_changed()

    def _handle_snippet_click(self, node: Dict[str, Any], target_hwnd: Optional[int]) -> None:
        """Appelé lors d'un clic gauche sur un extrait pour le coller."""
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Shift + Clic permet de renommer rapidement
            self._prompt_rename_snippet(node)
            return

        # 1. Remonter l'extrait utilisé en tête (après les épinglés)
        node_id = node.get("id")
        if node_id:
            self.storage.bump_snippet(node_id)
            if self.on_data_changed:
                self.on_data_changed()

        # 2. Coller le texte dans l'application cible
        content = node.get("content", "")
        self.on_select_paste(content, target_hwnd)

    def _prompt_rename_snippet(self, node: Dict[str, Any]) -> None:
        from PyQt6.QtWidgets import QInputDialog
        current_name = node.get("name", "")
        new_name, ok = QInputDialog.getText(
            None,
            "Renommer l'extrait",
            f"Nouveau nom pour '{current_name}' :",
            text=current_name
        )
        if ok and new_name.strip():
            self.storage.rename_snippet(node["id"], new_name.strip())
            if self.on_data_changed:
                self.on_data_changed()
