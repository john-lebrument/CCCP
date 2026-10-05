import os
import json
import tempfile
import unittest
from pathlib import Path

from app.storage import StorageManager
from app.win_hooks import parse_shortcut, MOD_CONTROL, MOD_ALT, MOD_SHIFT, MOD_NOREPEAT


class TestSmartClipboard(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp_dir.name) / "test_data.json"
        self.storage = StorageManager(data_file=self.data_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_snippets_loaded(self):
        snippets = self.storage.snippets
        self.assertGreater(len(snippets), 0)
        # Check that 'Emails' folder exists in defaults
        folder_names = [s.get("name") for s in snippets if s.get("type") == "folder"]
        self.assertIn("Emails", folder_names)

    def test_history_addition_and_deduplication(self):
        # Add 3 items
        self.storage.add_history("Premier texte")
        self.storage.add_history("Deuxième texte")
        # Add consecutive duplicate
        added_dup = self.storage.add_history("Deuxième texte")
        self.assertFalse(added_dup)
        self.assertEqual(len(self.storage.history), 2)
        self.assertEqual(self.storage.history[0]["content"], "Deuxième texte")

        # Add earlier item -> should move to top without duplicate
        self.storage.add_history("Premier texte")
        self.assertEqual(len(self.storage.history), 2)
        self.assertEqual(self.storage.history[0]["content"], "Premier texte")

    def test_history_max_limit(self):
        self.storage.settings["max_history"] = 5
        for i in range(10):
            self.storage.add_history(f"Texte {i}")
        self.assertEqual(len(self.storage.history), 5)
        self.assertEqual(self.storage.history[0]["content"], "Texte 9")

    def test_add_folder_and_snippet(self):
        # Create folder
        folder = self.storage.add_folder(None, "Mon Dossier Test")
        self.assertEqual(folder["name"], "Mon Dossier Test")
        self.assertEqual(folder["type"], "folder")

        # Create snippet inside folder
        snippet = self.storage.add_snippet(
            parent_folder_id=folder["id"],
            name="Mon Snippet Test",
            content="Bonjour tout le monde",
            shortcut="Ctrl+Alt+B"
        )
        self.assertEqual(snippet["name"], "Mon Snippet Test")
        self.assertEqual(snippet["content"], "Bonjour tout le monde")
        self.assertEqual(snippet["shortcut"], "Ctrl+Alt+B")

        # Check retrieval in flat list
        flat = self.storage.get_all_snippets_flat()
        found = [p for n, p in flat if n["id"] == snippet["id"]]
        self.assertTrue(len(found) > 0)
        self.assertIn("Mon Dossier Test > Mon Snippet Test", found[0])

    def test_update_and_delete_node(self):
        snippet = self.storage.add_snippet(None, "Snippet Modif", "Avant modif", "")
        snip_id = snippet["id"]

        # Update
        updated = self.storage.update_node(snip_id, name="Snippet Modifié", content="Après modif", shortcut="Ctrl+Alt+M")
        self.assertTrue(updated)
        node = self.storage._find_node_by_id(self.storage.snippets, snip_id)
        self.assertEqual(node["name"], "Snippet Modifié")
        self.assertEqual(node["content"], "Après modif")
        self.assertEqual(node["shortcut"], "Ctrl+Alt+M")

        # Delete
        deleted = self.storage.delete_node(snip_id)
        self.assertTrue(deleted)
        self.assertIsNone(self.storage._find_node_by_id(self.storage.snippets, snip_id))

    def test_pinned_snippets(self):
        s1 = self.storage.add_snippet(None, "Snippet 1", "Contenu 1", "", pinned=False)
        s2 = self.storage.add_snippet(None, "Snippet 2", "Contenu 2", "", pinned=True)

        pinned = self.storage.get_pinned_snippets()
        pinned_ids = [s["id"] for s in pinned]
        self.assertIn(s2["id"], pinned_ids)
        self.assertNotIn(s1["id"], pinned_ids)

        # Toggle s1 to pinned
        new_state = self.storage.toggle_pinned(s1["id"])
        self.assertTrue(new_state)
        pinned = self.storage.get_pinned_snippets()
        self.assertIn(s1["id"], [s["id"] for s in pinned])

        # Toggle s1 back to unpinned
        new_state2 = self.storage.toggle_pinned(s1["id"])
        self.assertFalse(new_state2)

    def test_set_snippets_reorder(self):
        new_tree = [
            {"id": "custom-1", "type": "snippet", "name": "Premier", "content": "1", "shortcut": ""},
            {"id": "custom-2", "type": "snippet", "name": "Second", "content": "2", "shortcut": ""},
        ]
        self.storage.set_snippets(new_tree)
        self.assertEqual(len(self.storage.snippets), 2)
        self.assertEqual(self.storage.snippets[0]["name"], "Premier")
        self.assertEqual(self.storage.snippets[1]["name"], "Second")

    def test_bump_snippet_after_pinned(self):
        # Setup: Pinned 1, Unpinned A, Unpinned B, Unpinned C
        folder = self.storage.add_folder(None, "Test Folder")
        fid = folder["id"]
        p1 = self.storage.add_snippet(fid, "P1", "P1 content", pinned=True)
        a = self.storage.add_snippet(fid, "A", "A content", pinned=False)
        b = self.storage.add_snippet(fid, "B", "B content", pinned=False)
        c = self.storage.add_snippet(fid, "C", "C content", pinned=False)

        # Bump C -> should move to index 1 (right after P1)
        res = self.storage.bump_snippet(c["id"])
        self.assertTrue(res)

        f_node = self.storage._find_node_by_id(self.storage.snippets, fid)
        child_names = [ch["name"] for ch in f_node["children"]]
        self.assertEqual(child_names, ["P1", "C", "A", "B"])

        # Add P2 (pinned)
        p2 = self.storage.add_snippet(fid, "P2", "P2 content", pinned=True)
        # Bumping B -> should move right after all pinned (P1, P2)
        self.storage.bump_snippet(b["id"])
        f_node = self.storage._find_node_by_id(self.storage.snippets, fid)
        child_names = [ch["name"] for ch in f_node["children"]]
        # P1, P2 are first (or P1... P2 was inserted at end or bumped), B is right after all pinned
        pinned_count = sum(1 for ch in f_node["children"] if ch.get("pinned"))
        self.assertEqual(f_node["children"][pinned_count]["name"], "B")

    def test_rename_snippet(self):
        s = self.storage.add_snippet(None, "Original Name", "content")
        res = self.storage.rename_snippet(s["id"], "Nouveau Nom")
        self.assertTrue(res)
        node = self.storage._find_node_by_id(self.storage.snippets, s["id"])
        self.assertEqual(node["name"], "Nouveau Nom")

    def test_export_and_import(self):
        self.storage.add_history("Ceci est un test export")
        export_path = Path(self.temp_dir.name) / "export.json"

        # Export
        success = self.storage.export_data(str(export_path), include_history=True)
        self.assertTrue(success)
        self.assertTrue(export_path.exists())

        with open(export_path, "r", encoding="utf-8") as f:
            exported_content = json.load(f)
        self.assertIn("snippets", exported_content)
        self.assertIn("history", exported_content)

        # Import into fresh storage
        new_data_file = Path(self.temp_dir.name) / "imported_data.json"
        new_storage = StorageManager(data_file=new_data_file)
        new_storage.clear_history()
        new_storage.snippets.clear()

        imported = new_storage.import_data(str(export_path), merge=False)
        self.assertTrue(imported)
        self.assertEqual(len(new_storage.history), 1)
        self.assertEqual(new_storage.history[0]["content"], "Ceci est un test export")

    def test_parse_shortcut(self):
        parsed = parse_shortcut("Ctrl+Alt+D")
        self.assertIsNotNone(parsed)
        mod, vk = parsed
        self.assertEqual(mod, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT)
        self.assertEqual(vk, ord('D'))

        parsed_f = parse_shortcut("F9")
        self.assertIsNotNone(parsed_f)
        mod_f, vk_f = parsed_f
        self.assertEqual(mod_f, MOD_NOREPEAT)
        self.assertEqual(vk_f, 0x78)  # VK_F9

        # Win + Numpad test
        parsed_win_num = parse_shortcut("Win+Num1")
        self.assertIsNotNone(parsed_win_num)
        mod_w, vk_w = parsed_win_num
        self.assertEqual(mod_w, 0x0008 | MOD_NOREPEAT)
        self.assertEqual(vk_w, 0x61)  # VK_NUMPAD1

        # Meta alias test
        parsed_meta_num = parse_shortcut("Meta+Num5")
        self.assertIsNotNone(parsed_meta_num)
        mod_m, vk_m = parsed_meta_num
        self.assertEqual(mod_m, 0x0008 | MOD_NOREPEAT)
        self.assertEqual(vk_m, 0x65)  # VK_NUMPAD5

    def test_get_all_folders_flat(self):
        folder1 = self.storage.add_folder(None, "Dossier 1")
        subfolder = self.storage.add_folder(folder1["id"], "Sous-dossier")
        folder2 = self.storage.add_folder(None, "Dossier 2")

        folders = self.storage.get_all_folders_flat()
        folder_paths = [path for fid, path in folders]
        self.assertIn("(Racine)", folder_paths)
        self.assertIn("Dossier 1", folder_paths)
        self.assertIn("Dossier 1 > Sous-dossier", folder_paths)
        self.assertIn("Dossier 2", folder_paths)

    def test_copyq_import_real_file(self):
        cpq_file = Path(r"C:\Data\script\Copier_Coller Gemini\import\1.cpq")
        if cpq_file.exists():
            new_data_file = Path(self.temp_dir.name) / "copyq_imported.json"
            new_storage = StorageManager(data_file=new_data_file)
            stats = new_storage.import_copyq_data(str(cpq_file), merge=False)
            self.assertEqual(stats["folders"], 7)
            self.assertGreater(stats["snippets"], 30)
            self.assertGreater(stats["history"], 200)
            # Verify specific tab and snippet
            lime_folder = [f for f in new_storage.snippets if f["name"] == "LimeSurvey"]
            self.assertEqual(len(lime_folder), 1)
            self.assertGreater(len(lime_folder[0]["children"]), 0)


if __name__ == "__main__":
    unittest.main()
