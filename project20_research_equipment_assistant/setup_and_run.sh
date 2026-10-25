#!/usr/bin/env bash
# LabSlot: create .venv, install dependencies, initialise the DB and start the app.
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python)
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip -q
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
python database.py
python app.py
