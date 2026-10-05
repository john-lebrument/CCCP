import sys
import os
from pathlib import Path

# Paths (portable mode aware)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "clipboard_data.json"

ICON_DIR = BASE_DIR / "Icone"
ICON_ICO = ICON_DIR / "icone.ico"
ICON_PNG = ICON_DIR / "icone.png"

APP_NAME = "cccp"
APP_TITLE = "CCCP - Couper, Copier, Coller, Persistant"
APP_VERSION = "1.3"

DEFAULT_MAX_HISTORY = 100
DEFAULT_TRIGGER_MOUSE = "Alt+RightClick"
DEFAULT_TRIGGER_HOTKEY = ""

DEFAULT_SNIPPETS = [
    {
        "id": "cat-email",
        "name": "Emails",
        "type": "folder",
        "children": [
            {
                "id": "cat-salutations",
                "name": "Salutations",
                "type": "folder",
                "children": [
                    {
                        "id": "snip-dispo",
                        "name": "Reste à disposition",
                        "type": "snippet",
                        "content": "Je reste à votre disposition pour tout renseignement complémentaire.",
                        "shortcut": "Ctrl+Alt+D"
                    },
                    {
                        "id": "snip-cordialement",
                        "name": "Bien cordialement",
                        "type": "snippet",
                        "content": "Bien cordialement,\n[Votre Nom]",
                        "shortcut": ""
                    },
                    {
                        "id": "snip-bonjour",
                        "name": "Bonjour cordial",
                        "type": "snippet",
                        "content": "Bonjour,\nJ'espère que vous allez bien.",
                        "shortcut": ""
                    }
                ]
            },
            {
                "id": "cat-reponses",
                "name": "Réponses rapides",
                "type": "folder",
                "children": [
                    {
                        "id": "snip-accuse",
                        "name": "Accusé de réception",
                        "type": "snippet",
                        "content": "J'accuse bonne réception de votre message et reviens vers vous dans les plus brefs délais.",
                        "shortcut": ""
                    }
                ]
            }
        ]
    },
    {
        "id": "cat-infos",
        "name": "Infos Utiles",
        "type": "folder",
        "children": [
            {
                "id": "snip-iban",
                "name": "Exemple Coordonnées",
                "type": "snippet",
                "content": "Adresse : 10 Rue Exemple, 75000 Paris\nTél : 01 23 45 67 89",
                "shortcut": ""
            }
        ]
    }
]
