import argparse
import sys
from pathlib import Path
from typing import Optional

# --- optionele imports uit jouw project (vallen terug als ze ontbreken) ---
try:
    from cncapp.excel_import import load_excel as project_load_excel  # type: ignore
except Exception:  # ImportError of andere fouten
    project_load_excel = None  # type: ignore

try:
    from cncapp.pipeline import run as project_pipeline_run  # type: ignore
except Exception:
    project_pipeline_run = None  # type: ignore

# --- third-party fallback ---
try:
    import pandas as pd
except Exception as e:
    print("Pandas ontbreekt of kan niet geladen worden. Installeer requirements:", file=sys.stderr)
    print("    python -m pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)


def load_excel_fallback(path: Path):
    """Fallback naar pandas als cncapp.excel_import.load_excel niet bestaat."""
    return pd.read_excel(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CLI voor CNC-profiles: lees Excel en (optioneel) run pipeline."
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=Path("sample_cutlist.xlsx"),
        help="Pad naar Excel-bestand (default: sample_cutlist.xlsx)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Aantal rijen tonen bij rooktest/preview (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alleen inlezen/preview, pipeline niet uitvoeren.",
    )
    args = parser.parse_args()

    excel_path: Path = args.excel
    if not excel_path.exists():
        print(f"❌ Bestand niet gevonden: {excel_path}", file=sys.stderr)
        return 1

    # 1) Excel inladen via project-functie als die bestaat, anders fallback
    try:
        if project_load_excel is not None:
            df = project_load_excel(excel_path)  # verwacht DataFrame
            source = "cncapp.excel_import.load_excel(...)"
        else:
            df = load_excel_fallback(excel_path)
            source = "pandas.read_excel(...) (fallback)"
    except Exception as e:
        print(f"❌ Fout bij lezen van {excel_path}: {e}", file=sys.stderr)
        return 1

    # 2) Rooktest / preview
    rows, cols = getattr(df, "shape", (None, None))
    print(f"✅ Excel gelezen via {source}: {excel_path} — {rows} rijen, {cols} kolommen")
    try:
        limit = max(0, int(args.limit))
    except Exception:
        limit = 5
    try:
        preview = df.head(limit).to_string(index=False)  # type: ignore[attr-defined]
        print(preview)
    except Exception:
        print("ℹ️ Kon geen preview tonen (geen DataFrame?).", file=sys.stderr)

    # 3) Pipeline aanroepen (indien aanwezig en niet --dry-run)
    if args.dry_run:
        print("ℹ️ --dry-run: pipeline wordt overgeslagen.")
        return 0

    if project_pipeline_run is None:
        print("ℹ️ Geen pipeline gevonden (cncapp.pipeline.run). Alleen rooktest gedaan.")
        return 0

    try:
        result = project_pipeline_run(df)  # type: ignore[call-arg]
        # We weten niet precies wat jouw pipeline teruggeeft; daarom defensief loggen:
        if result is None:
            print("✅ Pipeline uitgevoerd (result: None of geen return).")
        else:
            print(f"✅ Pipeline uitgevoerd. Result type: {type(result).__name__}")
            # als het een dict / lijst / str is, geven we beknopt weer:
            try:
                if isinstance(result, (str, int, float)):
                    print(f"Result: {result}")
                elif isinstance(result, dict):
                    keys = list(result.keys())
                    print(f"Result (dict-keys): {keys[:10]}{' ...' if len(keys)>10 else ''}")
                elif hasattr(result, '__len__'):
                    print(f"Result (len): {len(result)}")
            except Exception:
                pass
        return 0
    except Exception as e:
        print(f"❌ Fout tijdens pipeline-run: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
