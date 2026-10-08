#!/bin/bash
# Backup launcher: starts the app with a Terminal window showing its log.
# Quit by closing the app window.

cd "$(dirname "$0")" || exit 1

if [ ! -d ".venv" ]; then
  echo "No .venv folder found here. Create it first with:"
  echo "  python3.12 -m venv .venv"
  read -r -p "Press Return to close."
  exit 1
fi

source .venv/bin/activate

# First run only: install anything that's missing (takes a minute).
python -c "import streamlit, pandas, rocketcea, webview" 2>/dev/null || pip install -r requirements.txt


python desktop.py
