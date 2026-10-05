import os
import shutil
from pathlib import Path

VERSION = "1.3"
APP_BASE_NAME = "cccp"
EXE_NAME = f"{APP_BASE_NAME}_{VERSION}.exe"
FOLDER_NAME = f"{APP_BASE_NAME}_{VERSION}"

ROOT_DIR = Path(r"C:\Data\script\Copier_Coller Gemini")
SRC_DIST = ROOT_DIR / "dist" / FOLDER_NAME
SRC_DATA = ROOT_DIR / "data"
SRC_ICONE = ROOT_DIR / "Icone"

LOCAL_RELEASES = ROOT_DIR / "releases" / FOLDER_NAME
ONEDRIVE_VIBE_CODING = Path(r"D:\OneDrive - unicaen.fr\Setup 1D\Vibe Coding") / FOLDER_NAME
ONEDRIVE_LAST_VERSION_DIR = Path(r"D:\OneDrive - unicaen.fr\Setup 1D\__Last version")


def package():
    print(f"--- Packaging {FOLDER_NAME} ({EXE_NAME}) ---")

    # 1. Prepare local release directory
    if LOCAL_RELEASES.exists():
        shutil.rmtree(LOCAL_RELEASES)
    LOCAL_RELEASES.mkdir(parents=True, exist_ok=True)

    # 2. Copy dist contents (executable + _internal)
    for item in SRC_DIST.iterdir():
        dest = LOCAL_RELEASES / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # 3. Copy data directory (snippets + history)
    dest_data = LOCAL_RELEASES / "data"
    shutil.copytree(SRC_DATA, dest_data)

    # 4. Copy Icone directory
    dest_icone = LOCAL_RELEASES / "Icone"
    if SRC_ICONE.exists():
        shutil.copytree(SRC_ICONE, dest_icone)

    # 5. Add direct launcher script
    bat_file = LOCAL_RELEASES / f"Lancer_{APP_BASE_NAME}.bat"
    bat_file.write_text(f'@echo off\nstart "" "%~dp0{EXE_NAME}"\nexit\n', encoding="utf-8")

    # 6. Add README.txt
    readme_file = LOCAL_RELEASES / "README.txt"
    readme_content = f"""CCCP (Couper, Copier, Coller, Persistant) v{VERSION} - Application Portable
======================================================================

Exécutable principal : {EXE_NAME}

Lancement :
- Double-cliquez sur {EXE_NAME} ou Lancer_{APP_BASE_NAME}.bat.
- L'application se loge discrètement dans la barre des tâches (icône près de l'horloge Windows).

Nouveautés & Fonctionnalités (v{VERSION}) :
1. Titre & Identité :
   - CCCP - Couper, Copier, Coller, Persistant.
   - Icône personnalisée intégrée à l'application et à la barre des tâches.
2. Déclencheurs personnalisables :
   - Choix du clic souris pour ouvrir le menu : Alt+Clic Droit, Ctrl+Clic Droit, Clic Molette, Bouton Souris Précédent/Suivant, etc.
   - Raccourci clavier global d'ouverture sous le curseur (ex: Ctrl+Alt+V ou Win+Num0).
3. Raccourcis Windows & Pavé Numérique :
   - Prise en charge intégrale des raccourcis avec touche Windows (Win) et chiffres du pavé numérique (Win+Num1 .. Win+Num9).
   - Module de saisie intelligent avec bouton d'aide '⚡ Pavé Num'.
4. Suppression rapide des raccourcis :
   - Croix rouge ❌ au début de chaque ligne dans la vue globale des raccourcis.
5. Dépôt direct dans l'arborescence :
   - Clic droit sur l'aperçu du texte (ou tableau d'historique) > '📁 Déposer dans un dossier...' pour classer instantanément un extrait.
6. Replier / Déplier en 1 clic :
   - Bouton '🔽 Tout replier' / '▶️ Tout déplier' dans l'onglet extraits.
7. Portabilité complète :
   - Sauvegarde autonome dans le dossier 'data' local.
"""
    readme_file.write_text(readme_content, encoding="utf-8")

    print(f"Local package created at: {LOCAL_RELEASES}")

    # 7. Copy to OneDrive Vibe Coding destination
    ONEDRIVE_VIBE_CODING.parent.mkdir(parents=True, exist_ok=True)
    print(f"Copying to {ONEDRIVE_VIBE_CODING}...")
    shutil.copytree(LOCAL_RELEASES, ONEDRIVE_VIBE_CODING, dirs_exist_ok=True)
    print("Success! Vibe Coding destination updated.")

    # 8. Copy to OneDrive __Last version
    if ONEDRIVE_LAST_VERSION_DIR.exists():
        # A. Copy standalone executable
        dest_exe = ONEDRIVE_LAST_VERSION_DIR / EXE_NAME
        print(f"Copying executable to {dest_exe}...")
        shutil.copy2(LOCAL_RELEASES / EXE_NAME, dest_exe)

        # B. Copy full portable folder
        dest_last_folder = ONEDRIVE_LAST_VERSION_DIR / FOLDER_NAME
        print(f"Copying portable folder to {dest_last_folder}...")
        shutil.copytree(LOCAL_RELEASES, dest_last_folder, dirs_exist_ok=True)
        print("Success! __Last version updated.")


if __name__ == "__main__":
    package()
