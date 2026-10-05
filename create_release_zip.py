import os
import shutil
import zipfile
import json
from pathlib import Path
from app.config import DEFAULT_SNIPPETS

ROOT = Path(__file__).parent
DIST_APP = ROOT / "dist" / "cccp_1.3"
ZIP_OUTPUT = ROOT / "dist" / "CCCP_v1.3_Portable.zip"
STAGING_ROOT = ROOT / "dist" / "staging_portable"
STAGING = STAGING_ROOT / "CCCP_v1.3_Portable"

def main():
    if STAGING_ROOT.exists():
        shutil.rmtree(STAGING_ROOT)
    STAGING.mkdir(parents=True, exist_ok=True)

    print("Copying dist files...")
    shutil.copytree(DIST_APP, STAGING, dirs_exist_ok=True)

    src_icone = ROOT / "Icone"
    if src_icone.exists():
        shutil.copytree(src_icone, STAGING / "Icone", dirs_exist_ok=True)

    bat_file = STAGING / "Lancer_cccp.bat"
    bat_file.write_text('@echo off\nstart "" "%~dp0cccp_1.3.exe"\nexit\n', encoding="utf-8")

    data_dir = STAGING / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    clean_data = {
        "version": "1.0",
        "settings": {
            "max_history": 100,
            "trigger_mouse": "Alt+RightClick",
            "trigger_hotkey": "",
            "enable_shortcuts": True
        },
        "history": [],
        "snippets": DEFAULT_SNIPPETS
    }
    with open(data_dir / "clipboard_data.json", "w", encoding="utf-8") as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)

    readme_file = STAGING / "README.txt"
    readme_file.write_text(
        "CCCP (Couper, Copier, Coller, Persistant) v1.3 - Portable\n"
        "======================================================\n\n"
        "Lancement :\n"
        "- Double-cliquez sur 'cccp_1.3.exe' ou 'Lancer_cccp.bat'.\n"
        "- L'application se loge discrètement près de l'horloge Windows.\n"
        "- Pressez Alt + Clic Droit dans n'importe quelle application pour coller un extrait ou un historique !\n",
        encoding="utf-8"
    )

    print("Creating ZIP archive...")
    with zipfile.ZipFile(ZIP_OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(STAGING):
            for file in files:
                full_p = Path(root) / file
                rel_p = full_p.relative_to(STAGING_ROOT)
                zf.write(full_p, rel_p)

    mb = round(ZIP_OUTPUT.stat().st_size / (1024 * 1024), 2)
    print(f"Archive successfully created: {ZIP_OUTPUT} ({mb} MB)")

if __name__ == "__main__":
    main()
