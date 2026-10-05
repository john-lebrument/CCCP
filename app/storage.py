import json
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.config import DATA_DIR, DATA_FILE, DEFAULT_MAX_HISTORY, DEFAULT_SNIPPETS


class StorageManager:
    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or DATA_FILE
        self.history: List[Dict[str, Any]] = []
        self.snippets: List[Dict[str, Any]] = []
        self.settings: Dict[str, Any] = {
            "max_history": DEFAULT_MAX_HISTORY,
            "alt_right_click": True,
            "enable_shortcuts": True,
        }
        self.load()

    def load(self) -> None:
        """Load data from JSON file or initialize with defaults."""
        if not self.data_file.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.history = []
            self.snippets = list(DEFAULT_SNIPPETS)
            self.save()
            return

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.history = data.get("history", [])
                self.snippets = data.get("snippets", list(DEFAULT_SNIPPETS))
                self.settings.update(data.get("settings", {}))
        except Exception as e:
            print(f"[Storage] Error loading data: {e}. Using defaults.")
            self.history = []
            self.snippets = list(DEFAULT_SNIPPETS)

    def save(self) -> None:
        """Persist current state to JSON file."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            temp_file = self.data_file.with_suffix(".tmp")
            data = {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "settings": self.settings,
                "history": self.history,
                "snippets": self.snippets,
            }
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_file.replace(self.data_file)
        except Exception as e:
            print(f"[Storage] Error saving data: {e}")

    # --- History Management ---
    def add_history(self, content: str) -> bool:
        """Add text to history. Return True if added, False if duplicate of latest item."""
        if not content or not content.strip():
            return False

        # If already same as latest, don't duplicate
        if self.history and self.history[0].get("content") == content:
            return False

        # Remove existing occurrence if present further down to bring it to top
        self.history = [item for item in self.history if item.get("content") != content]

        item = {
            "id": str(uuid.uuid4()),
            "content": content,
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "time_epoch": time.time(),
            "length": len(content),
        }
        self.history.insert(0, item)

        # Enforce max history limit
        max_h = int(self.settings.get("max_history", DEFAULT_MAX_HISTORY))
        if len(self.history) > max_h:
            self.history = self.history[:max_h]

        self.save()
        return True

    def remove_history_item(self, item_id: str) -> None:
        self.history = [item for item in self.history if item.get("id") != item_id]
        self.save()

    def clear_history(self) -> None:
        self.history.clear()
        self.save()

    # --- Snippets Tree Management ---
    def get_all_snippets_flat(self) -> List[Tuple[Dict[str, Any], str]]:
        """Return flat list of (snippet_node, 'Folder > SubFolder > Snippet Name')."""
        results = []

        def _traverse(nodes: List[Dict[str, Any]], current_path: str):
            for node in nodes:
                node_type = node.get("type", "snippet")
                name = node.get("name", "Sans nom")
                path = f"{current_path} > {name}" if current_path else name
                if node_type == "folder":
                    _traverse(node.get("children", []), path)
                else:
                    results.append((node, path))

        _traverse(self.snippets, "")
        return results

    def get_all_folders_flat(self) -> List[Tuple[Optional[str], str]]:
        """Return flat list of (folder_id or None, 'Folder > SubFolder') with (None, '(Racine)') first."""
        results = [(None, "(Racine)")]

        def _traverse(nodes: List[Dict[str, Any]], current_path: str):
            for node in nodes:
                if node.get("type") == "folder":
                    name = node.get("name", "Dossier sans nom")
                    path = f"{current_path} > {name}" if current_path else name
                    results.append((node.get("id"), path))
                    _traverse(node.get("children", []), path)

        _traverse(self.snippets, "")
        return results

    def get_snippets_with_shortcuts(self) -> List[Dict[str, Any]]:
        """Return all snippets that have an assigned shortcut."""
        flat = self.get_all_snippets_flat()
        return [node for node, path in flat if node.get("shortcut")]

    def get_pinned_snippets(self) -> List[Dict[str, Any]]:
        """Return all snippets marked as pinned (ordered)."""
        flat = self.get_all_snippets_flat()
        return [node for node, path in flat if node.get("pinned", False)]

    def toggle_pinned(self, node_id: str) -> bool:
        """Toggle pinned state for a snippet. Returns new pinned state."""
        node = self._find_node_by_id(self.snippets, node_id)
        if node and node.get("type") == "snippet":
            new_state = not node.get("pinned", False)
            node["pinned"] = new_state
            if new_state:
                self.bump_snippet(node_id)
            else:
                self.save()
            return new_state
        return False

    def set_snippets(self, new_snippets: List[Dict[str, Any]]) -> None:
        """Update the entire snippets tree (e.g. after drag-and-drop reordering)."""
        self.snippets = new_snippets
        self.save()

    def bump_snippet(self, node_id: str) -> bool:
        """
        Move a snippet to the top of its list / container.
        If there are pinned items, it is placed immediately after the pinned items.
        If the snippet itself is pinned, it is placed at the top of pinned items.
        """
        def _find_and_bump(nodes: List[Dict[str, Any]]) -> bool:
            for i, n in enumerate(nodes):
                if n.get("id") == node_id and n.get("type") == "snippet":
                    target = nodes.pop(i)
                    if target.get("pinned", False):
                        nodes.insert(0, target)
                    else:
                        insert_idx = 0
                        while insert_idx < len(nodes) and nodes[insert_idx].get("pinned", False):
                            insert_idx += 1
                        nodes.insert(insert_idx, target)
                    return True
                if n.get("type") == "folder" and "children" in n:
                    if _find_and_bump(n["children"]):
                        return True
            return False

        res = _find_and_bump(self.snippets)
        if res:
            self.save()
        return res

    def rename_snippet(self, node_id: str, new_name: str) -> bool:
        """Rename a snippet or folder."""
        clean_name = new_name.strip()
        if not clean_name:
            return False
        return self.update_node(node_id, name=clean_name)

    def add_snippet(self, parent_folder_id: Optional[str], name: str, content: str, shortcut: str = "", pinned: bool = False) -> Dict[str, Any]:
        """Add a new snippet node inside a folder (or root if None)."""
        new_node = {
            "id": str(uuid.uuid4()),
            "type": "snippet",
            "name": name,
            "content": content,
            "shortcut": shortcut.strip(),
            "pinned": bool(pinned),
        }
        target_list = self.snippets
        if parent_folder_id:
            folder = self._find_node_by_id(self.snippets, parent_folder_id)
            if folder and folder.get("type") == "folder":
                target_list = folder.setdefault("children", [])

        if pinned:
            p_idx = 0
            while p_idx < len(target_list) and target_list[p_idx].get("pinned", False):
                p_idx += 1
            target_list.insert(p_idx, new_node)
        else:
            target_list.append(new_node)

        self.save()
        return new_node

    def add_folder(self, parent_folder_id: Optional[str], name: str) -> Dict[str, Any]:
        """Add a new folder node."""
        new_folder = {
            "id": str(uuid.uuid4()),
            "type": "folder",
            "name": name,
            "children": [],
        }
        if not parent_folder_id:
            self.snippets.append(new_folder)
        else:
            parent = self._find_node_by_id(self.snippets, parent_folder_id)
            if parent and parent.get("type") == "folder":
                parent.setdefault("children", []).append(new_folder)
            else:
                self.snippets.append(new_folder)
        self.save()
        return new_folder

    def update_node(self, node_id: str, **kwargs) -> bool:
        """Update node attributes (e.g. name, content, shortcut)."""
        node = self._find_node_by_id(self.snippets, node_id)
        if node:
            for k, v in kwargs.items():
                node[k] = v
            self.save()
            return True
        return False

    def delete_node(self, node_id: str) -> bool:
        """Remove a node (folder or snippet) from the tree."""
        def _delete(nodes: List[Dict[str, Any]]) -> bool:
            for i, n in enumerate(nodes):
                if n.get("id") == node_id:
                    nodes.pop(i)
                    return True
                if n.get("type") == "folder" and "children" in n:
                    if _delete(n["children"]):
                        return True
            return False

        res = _delete(self.snippets)
        if res:
            self.save()
        return res

    def _find_node_by_id(self, nodes: List[Dict[str, Any]], node_id: str) -> Optional[Dict[str, Any]]:
        for n in nodes:
            if n.get("id") == node_id:
                return n
            if n.get("type") == "folder" and "children" in n:
                found = self._find_node_by_id(n["children"], node_id)
                if found:
                    return found
        return None

    # --- Export / Import ---
    def export_data(self, target_path: str, include_history: bool = True) -> bool:
        try:
            export_dict = {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "settings": self.settings,
                "snippets": self.snippets,
            }
            if include_history:
                export_dict["history"] = self.history
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(export_dict, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[Storage] Export error: {e}")
            return False

    def import_data(self, source_path: str, merge: bool = False) -> bool:
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            new_snippets = data.get("snippets", [])
            new_history = data.get("history", [])

            if merge:
                # Merge snippets (append to root)
                self.snippets.extend(new_snippets)
                # Merge history without duplicates
                existing_contents = {h.get("content") for h in self.history}
                for h in new_history:
                    if h.get("content") not in existing_contents:
                        self.history.append(h)
            else:
                self.snippets = new_snippets
                if new_history:
                    self.history = new_history

            self.save()
            return True
        except Exception as e:
            print(f"[Storage] Import error: {e}")
            return False

    def import_copyq_data(self, cpq_path: str, merge: bool = True) -> Dict[str, int]:
        """Import history and categorized snippets from a CopyQ .cpq export file."""
        from app.copyq_importer import parse_copyq_export

        parsed = parse_copyq_export(cpq_path)
        folders_data = parsed.get("folders", [])
        history_data = parsed.get("history", [])

        stats = {
            "folders": len(folders_data),
            "snippets": sum(len(f.get("snippets", [])) for f in folders_data),
            "history": len(history_data),
        }

        if not merge:
            self.snippets = []
            self.history = []

        # Import folders and snippets
        for f_data in folders_data:
            folder_name = f_data["name"]
            # Find or create folder
            existing_folder = None
            if merge:
                for node in self.snippets:
                    if node.get("type") == "folder" and node.get("name") == folder_name:
                        existing_folder = node
                        break

            if not existing_folder:
                existing_folder = {
                    "id": str(uuid.uuid4()),
                    "type": "folder",
                    "name": folder_name,
                    "children": [],
                }
                self.snippets.append(existing_folder)

            for s_data in f_data.get("snippets", []):
                # Avoid exact duplicate in same folder
                children = existing_folder.setdefault("children", [])
                if not any(c.get("content") == s_data["content"] for c in children):
                    children.append({
                        "id": str(uuid.uuid4()),
                        "type": "snippet",
                        "name": s_data["name"],
                        "content": s_data["content"],
                        "shortcut": s_data.get("shortcut", ""),
                    })

        # Import history (reverse so newest are first)
        existing_history_texts = {h.get("content") for h in self.history}
        for text in reversed(history_data):
            if text and text not in existing_history_texts:
                item = {
                    "id": str(uuid.uuid4()),
                    "content": text,
                    "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "time_epoch": time.time(),
                    "length": len(text),
                }
                self.history.insert(0, item)
                existing_history_texts.add(text)

        # Enforce max history limit if set
        max_h = int(self.settings.get("max_history", DEFAULT_MAX_HISTORY))
        # For initial import, if CopyQ has more, allow it or clamp to max_h
        if len(self.history) > max_h:
            # If user has lots of history from copyq, expand max_history to match so we don't drop their items!
            self.settings["max_history"] = len(self.history)

        self.save()
        return stats
