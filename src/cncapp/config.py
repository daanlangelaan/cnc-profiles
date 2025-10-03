from pathlib import Path

# Minimale, veilige defaults (kan later uitgebreid worden)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT
DEFAULT_EXCEL = PROJECT_ROOT / "sample_cutlist.xlsx"
DEFAULT_SHEET = 0
