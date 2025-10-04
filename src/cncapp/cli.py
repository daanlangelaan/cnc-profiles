import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

DEBUG = False

project_load_excel = None
project_pipeline_run = None
project_to_profiles = None
project_generate_gcode = None

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
    from cncapp.gcode import generate_gcode as project_generate_gcode  # type: ignore
except Exception:
    if DEBUG:
        print("Import note: cncapp.gcode.generate_gcode niet gevonden; --gcode wordt genegeerd.", file=sys.stderr)
        traceback.print_exc()

try:
    import pandas as pd
except Exception:
    print("Pandas ontbreekt. Installeer dependencies met:")
    print("    python -m pip install -r requirements.txt")
    raise SystemExit(2)


def load_excel_fallback(path: Path):
    return pd.read_excel(path, sheet_name=0)


def _export_df(df: "pd.DataFrame", out_path: Path) -> str:
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
    try:
        if hasattr(x, "model_dump"):
            return x.model_dump()
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
    if isinstance(x, list):
        return [_to_serializable(i) for i in x]
    if isinstance(x, dict):
        return {k: _to_serializable(v) for k, v in x.items()}
    return x


def _export_profiles(objs: list, out_path: Path) -> str:
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = _to_serializable(objs)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI: lees Excel → (optioneel) export / pipeline / profielen / gcode.")
    parser.add_argument("--excel", type=Path, default=Path("sample_cutlist.xlsx"), help="Pad naar Excel-bestand")
    parser.add_argument("--limit", type=int, default=5, help="Aantal rijen in preview (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Alleen preview, pipeline niet draaien")
    parser.add_argument("--out", type=Path, help="Exporteer opgeschoonde tabel (.csv/.xlsx/.json)")
    parser.add_argument("--profiles", type=Path, help="Exporteer geparste profielen naar JSON")
    parser.add_argument("--gcode", type=Path, help="Combineer alle profielen tot één G-code bestand (.nc)")
    args = parser.parse_args()

    if not args.excel.exists():
        print(f"❌ Bestand niet gevonden: {args.excel}", file=sys.stderr)
        return 1

    # 1) Excel
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

    try:
        print(df.head(max(0, int(args.limit))).to_string(index=False))
    except Exception:
        print("ℹ️ Kon geen preview tonen (geen DataFrame?).", file=sys.stderr)

    # 2) Export tabel
    if args.out:
        try:
            out_file = _export_df(df, args.out)
            print(f"💾 Tabel geëxporteerd naar: {out_file}")
        except Exception as e:
            print(f"❌ Export mislukt: {e}", file=sys.stderr)
            if DEBUG:
                traceback.print_exc()
            return 1

    # 3) Profielen
    profs = None
    if args.profiles or args.gcode:
        if project_to_profiles is None:
            print("❌ Profielen gevraagd maar to_profiles ontbreekt.", file=sys.stderr)
            return 1
        try:
            profs = project_to_profiles(df)
        except Exception as e:
            print(f"❌ Fout bij profielen maken: {e}", file=sys.stderr)
            if DEBUG:
                traceback.print_exc()
            return 1

    if args.profiles and profs is not None:
        try:
            pfile = _export_profiles(profs, args.profiles)
            print(f"🧩 Profielen geëxporteerd naar: {pfile}  (items: {len(profs)})")
        except Exception as e:
            print(f"❌ Fout bij profielen export: {e}", file=sys.stderr)
            if DEBUG:
                traceback.print_exc()
            return 1

    # 4) G-code
    if args.gcode:
        if project_generate_gcode is None:
            print("❌ --gcode opgegeven maar cncapp.gcode.generate_gcode ontbreekt.", file=sys.stderr)
            return 1
        try:
            code = project_generate_gcode(profs or [], None)
            args.gcode.parent.mkdir(parents=True, exist_ok=True)
            args.gcode.write_text(code, encoding="utf-8")
            print(f"🛠️  G-code geschreven naar: {args.gcode}")
        except Exception as e:
            print(f"❌ Fout bij G-code genereren: {e}", file=sys.stderr)
            if DEBUG:
                traceback.print_exc()
            return 1

    # 5) Pipeline
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
