import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

# Debug-logging voor importproblemen (zet op True als je wilt meekijken)
DEBUG = False

# Probeer project-implementaties te importeren; val terug op pandas
project_load_excel = None
project_pipeline_run = None
project_to_profiles = None

try:
    from cncapp.excel_import import load_excel as project_load_excel  # type: ignore
    from cncapp.excel_import import to_profiles as project_to_profiles  # type: ignore
except Exception:
    if DEBUG:
        print("Import note: cncapp.excel_import niet geladen, fallback naar pandas.", file=sys.stderr)
        traceback.print_exc()

try:
    from cncapp.pipeline import run as project_pipeline_run  # type: ignore
except Exception:
    if DEBUG:
        print("Import note: cncapp.pipeline niet geladen, pipeline wordt overgeslagen.", file=sys.stderr)
        traceback.print_exc()

try:
    import pandas as pd
except Exception:
    print("Pandas ontbreekt. Installeer dependencies met:", file=sys.stderr)
    print("    python -m pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)


def load_excel_fallback(path: Path):
    return pd.read_excel(path, sheet_name=0)


def _export_df(df: "pd.DataFrame", out_path: Path) -> str:
    """Schrijf DataFrame weg op basis van extensie (.csv / .xlsx / .json)."""
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ext = out_path.suffix.lower()

    if ext == ".csv":
        df.to_csv(out_path, index=False)
    elif ext in {".xlsx", ".xlsm"}:
        df.to_excel(out_path, index=False)
    elif ext == ".json":
        df.to_json(out_path, orient="records", indent=2, force_ascii=False)
    else:
        raise ValueError(f"Niet-ondersteunde extensie: {ext} (gebruik .csv, .xlsx of .json)")
    return str(out_path)


def _to_serializable(x: Any) -> Any:
    """
    Maak pydantic/datataclass/custom objecten JSON-serialiseerbaar.
    - pydantic v2: model_dump()
    - pydantic v1: dict()
    - dataclass: asdict()
    - fallback: __dict__ of str(x)
    """
    try:
        # pydantic v2
        if hasattr(x, "model_dump"):
            return x.model_dump()
        # pydantic v1
        if hasattr(x, "dict"):
            return x.dict()
    except Exception:
        pass

    try:
        from dataclasses import is_dataclass, asdict
        if is_dataclass(x):
            return asdict(x)
    except Exception:
        pass

    if hasattr(x, "__dict__"):
        try:
            return {k: _to_serializable(v) for k, v in x.__dict__.items()}
        except Exception:
            return str(x)

    # Lists / dicts recursief
    if isinstance(x, list):
        return [_to_serializable(i) for i in x]
    if isinstance(x, dict):
        return {k: _to_serializable(v) for k, v in x.items()}

    return x


def _export_profiles(objs: list, out_path: Path) -> str:
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = _to_serializable(objs)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI: lees Excel → (optioneel) export/ pipeline/ profielen.")
    parser.add_argument("--excel", type=Path, default=Path("sample_cutlist.xlsx"), help="Pad naar Excel-bestand")
    parser.add_argument("--limit", type=int, default=5, help="Aantal rijen in preview (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Alleen preview, pipeline niet draaien")
    parser.add_argument(
        "--out",
        type=Path,
        help="Exporteer opgeschoonde tabel (ext bepaalt type: .csv / .xlsx / .json). Voorbeeld: --out out/cleaned.csv",
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        help="Exporteer geparste profielen naar JSON. Voorbeeld: --profiles out/profiles.json",
    )
    args = parser.parse_args()

    if not args.excel.exists():
        print(f"❌ Bestand niet gevonden: {args.excel}", file=sys.stderr)
        return 1

    # 1) Excel inlezen
    try:
        if project_load_excel is not None:
            df = project_load_excel(args.excel)
            source = "cncapp.excel_import.load_excel(...)"
        else:
            df = load_excel_fallback(args.excel)
            source = "pandas.read_excel(...) (fallback)"
    except Exception as e:
        print(f"❌ Fout bij lezen van {args.excel}: {e}", file=sys.stderr)
        if DEBUG:
            traceback.print_exc()
        return 1

    rows, cols = getattr(df, "shape", (None, None))
    print(f"✅ Excel gelezen via {source}: {args.excel} — {rows} rijen, {cols} kolommen")

    # Preview
    try:
        print(df.head(max(0, int(args.limit))).to_string(index=False))
    except Exception:
        print("ℹ️ Kon geen preview tonen (geen DataFrame?).", file=sys.stderr)

    # Export tabel (optioneel)
    if args.out:
        try:
            out_file = _export_df(df, args.out)
            print(f"💾 Tabel geëxporteerd naar: {out_file}")
        except Exception as e:
            print(f"❌ Export mislukt: {e}", file=sys.stderr)
            if DEBUG:
                traceback.print_exc()
            return 1

    # Profielen export (optioneel)
    if args.profiles:
        if project_to_profiles is None:
            print("❌ Profiel-export gevraagd maar cncapp.excel_import.to_profiles ontbreekt.", file=sys.stderr)
            return 1
        try:
            profs = project_to_profiles(df)  # -> list[ProfileSpec]
            pfile = _export_profiles(profs, args.profiles)
            print(f"🧩 Profielen geëxporteerd naar: {pfile}  (items: {len(profs)})")
        except Exception as e:
            print(f"❌ Fout bij profielen export: {e}", file=sys.stderr)
            if DEBUG:
                traceback.print_exc()
            return 1

    # 2) Pipeline
    if args.dry_run:
        print("ℹ️ --dry-run: pipeline wordt overgeslagen.")
        return 0

    if project_pipeline_run is None:
        print("ℹ️ Geen pipeline gevonden (cncapp.pipeline.run). Alleen rooktest gedaan.")
        return 0

    try:
        result = project_pipeline_run(df)  # type: ignore[arg-type]
        print("✅ Pipeline uitgevoerd.", f"Result type: {type(result).__name__}" if result is not None else "(geen return)")
        return 0
    except Exception as e:
        print(f"❌ Fout tijdens pipeline-run: {e}", file=sys.stderr)
        if DEBUG:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
