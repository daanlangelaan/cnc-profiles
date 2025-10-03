import argparse
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Pandas ontbreekt. Run: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)

def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test: lees een Excel cutlist en geef een korte samenvatting.")
    parser.add_argument("--excel", type=Path, default=Path("sample_cutlist.xlsx"),
                        help="Pad naar Excel bestand (default: sample_cutlist.xlsx)")
    args = parser.parse_args()

    if not args.excel.exists():
        print(f"Bestand niet gevonden: {args.excel}", file=sys.stderr)
        return 1

    try:
        df = pd.read_excel(args.excel)
    except Exception as e:
        print(f"Fout bij lezen van {args.excel}: {e}", file=sys.stderr)
        return 1

    rows, cols = df.shape
    print(f"✅ Excel gelezen: {args.excel} — {rows} rijen, {cols} kolommen")
    print(df.head(3).to_string(index=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
