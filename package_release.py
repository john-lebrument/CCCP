"""Build a clean, portable CCCP package from a PyInstaller folder build.

The package intentionally does not copy the developer's local data/ directory:
clipboard history and custom snippets must never be bundled into a public release.
"""

import argparse
import shutil
from pathlib import Path

VERSION = "1.3"
APP_BASE_NAME = "cccp"
EXE_NAME = f"{APP_BASE_NAME}_{VERSION}.exe"
FOLDER_NAME = f"{APP_BASE_NAME}_{VERSION}"
ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_SRC_DIST = ROOT_DIR / "dist" / FOLDER_NAME
DEFAULT_OUTPUT_DIR = ROOT_DIR / "releases" / FOLDER_NAME


def package(source_dist: Path, output_dir: Path, replace: bool = False) -> Path:
    """Assemble a portable package without copying user data or machine paths."""
    source_dist = source_dist.resolve()
    output_dir = output_dir.resolve()
    if not source_dist.is_dir():
        raise FileNotFoundError(f"Build folder not found: {source_dist}")
    if output_dir.exists():
        if not replace:
            raise FileExistsError(
                f"Output folder already exists: {output_dir}. Use --replace to overwrite it."
            )
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True)
    for item in source_dist.iterdir():
        # A prior build may contain user state. Never copy it into a release.
        if item.name.lower() == "data":
            continue
        destination = output_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)

    icon_dir = ROOT_DIR / "Icone"
    if icon_dir.is_dir():
        shutil.copytree(icon_dir, output_dir / "Icone")

    launcher = output_dir / f"Lancer_{APP_BASE_NAME}.bat"
    launcher.write_text(
        f'@echo off\nstart "" "%~dp0{EXE_NAME}"\nexit\n',
        encoding="utf-8",
    )
    readme = output_dir / "README.txt"
    readme.write_text(
        f"CCCP (Couper, Copier, Coller, Persistant) v{VERSION} - Application portable\n"
        f"\nExécutable principal : {EXE_NAME}\n"
        f"\nLancement : double-cliquez sur {EXE_NAME} ou Lancer_{APP_BASE_NAME}.bat.\n"
        "\nLes données personnelles (historique du presse-papier et extraits) sont "
        "créées localement au premier lancement et ne sont pas incluses dans cette archive.\n",
        encoding="utf-8",
    )
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dist", type=Path, default=DEFAULT_SRC_DIST,
                        help="PyInstaller folder build (default: dist/cccp_1.3)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Package destination (default: releases/cccp_1.3)")
    parser.add_argument("--replace", action="store_true",
                        help="Replace an existing output folder")
    args = parser.parse_args()
    result = package(args.source_dist, args.output_dir, args.replace)
    print(f"Portable package created at: {result}")


if __name__ == "__main__":
    main()
