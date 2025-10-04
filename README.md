# CNC Profiles

[![Run Python tests](https://github.com/daanlangelaan/cnc-profiles/actions/workflows/tests.yml/badge.svg)](https://github.com/daanlangelaan/cnc-profiles/actions/workflows/tests.yml)

Tools for importing CNC profile cut-lists from Excel and generating machine-ready outputs.


## 🚀 Features
- Import from Excel (`sample_cutlist.xlsx`)
- Clean data models and pipeline structure (`src/cncapp/`)
- Ready for unit tests (`tests/`)

## 📦 Install (Windows)
```powershell
# clone
git clone https://github.com/daanlangelaan/cnc-profiles.git
cd cnc-profiles

# (optioneel) virtuele omgeving
python -m venv .venv
. .\.venv\Scripts\Activate.ps1

# dependencies
pip install -r requirements.txt
