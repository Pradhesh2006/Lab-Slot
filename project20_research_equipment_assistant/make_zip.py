"""Bundle the LabSlot project into project20_research_equipment_assistant.zip.

Usage:  python make_zip.py [--out PATH]

The archive is written next to the project folder (its parent directory) by
default, so it never contains itself. Excluded: __pycache__, .venv, venv, .env, .git
(plus .pyc files, local .db files and any previous zip).
--include-venv bundles a virtual environment, but venvs are tied to one OS/Python and are not portable;
the setup_and_run scripts are the reliable way to recreate it.
"""

import argparse
import os
import zipfile

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_NAME = "project20_research_equipment_assistant"
EXCLUDED_DIRS = {"__pycache__", ".venv", "venv", ".git"}
VENV_DIRS = {".venv", "venv"}
EXCLUDED_FILES = {".env"}


def should_skip_file(name):
    return name in EXCLUDED_FILES or name.endswith((".pyc", ".zip", ".db"))


def main():
    parser = argparse.ArgumentParser(description="Create the LabSlot project ZIP archive.")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(PROJECT_DIR), f"{PROJECT_NAME}.zip"),
                        help="output ZIP path (default: next to the project folder)")
    parser.add_argument("--include-venv", action="store_true",
                        help="also bundle .venv/venv (only works on the same OS/Python that created it)")
    args = parser.parse_args()
    excluded = EXCLUDED_DIRS - (VENV_DIRS if args.include_venv else set())
    out_path = os.path.abspath(args.out)

    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(PROJECT_DIR):
            dirs[:] = sorted(d for d in dirs if d not in excluded)
            for name in sorted(files):
                full = os.path.join(root, name)
                if should_skip_file(name) or os.path.abspath(full) == out_path:
                    continue
                arcname = os.path.join(PROJECT_NAME, os.path.relpath(full, PROJECT_DIR))
                archive.write(full, arcname)
                count += 1
    print(f"LabSlot package created: {out_path} ({count} files)")


if __name__ == "__main__":
    main()
