from __future__ import annotations
from pathlib import Path
from typing import Union, List, Dict
import re
import pandas as pd

from .models import ProfileSpec  # optioneel gebruikt

# Mapping naar vaste kolomnamen
COL_MAP_CANON = {
    "profiel_naam": "profiel_naam",
    "profiel": "profiel_naam",
    "profielnaam": "profiel_naam",
    "profiel_type": "profiel_type",
    "type": "profiel_type",
    "orientatie": "orientatie",
    "oriëntatie": "orientatie",
    "lengte_mm": "lengte_mm",
    "lengte": "lengte_mm",
    "aantal": "aantal",            # gebruiken we niet meer
    "zijde": "zijde",
    "gaten_x@d_mm": "gaten_x@d_mm",
    "gaten": "gaten_x@d_mm",
    "grote_kast": "grote_kast",
    "grote kast": "grote_kast",
}

def _norm_col(c: str) -> str:
    c = str(c).strip().lower()
    c = c.replace(" ", "_").replace("-", "_")
    c = c.replace("ë", "e").replace("ï", "i").replace("é", "e")
    return c

def _clean_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [_norm_col(c) for c in df.columns]
    cols = [COL_MAP_CANON.get(c, c) for c in cols]
    df.columns = cols
    # gooi volledig lege Unnamed-kolommen weg
    drop_cols = [c for c in df.columns if c.startswith("unnamed") and df[c].isna().all()]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    return df

def _combine_hole_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Bundel alle kolommen met '@' in één kolom 'gaten_x@d_mm'."""
    if "gaten_x@d_mm" not in df.columns:
        df["gaten_x@d_mm"] = None

    hole_like: List[str] = ["gaten_x@d_mm"]
    for c in df.columns:
        if c == "gaten_x@d_mm":
            continue
        try:
            if df[c].astype(str).str.contains("@", na=False).any():
                hole_like.append(c)
        except Exception:
            continue

    if len(hole_like) > 1:
        def join_row(row):
            parts = []
            for c in hole_like:
                v = row.get(c, None)
                if pd.notna(v):
                    s = str(v).strip()
                    if s and s.lower() != "nan":
                        parts.append(s)
            return " | ".join(parts) if parts else None

        df["gaten_x@d_mm"] = df[hole_like].apply(join_row, axis=1)
        df = df.drop(columns=[c for c in hole_like if c != "gaten_x@d_mm"])
    return df

def load_excel(path: Union[str, Path]) -> pd.DataFrame:
    """
    - 1 rij per 'zijde'
    - forward-fill basisvelden (zonder 'aantal')
    - 'aantal' wordt verwijderd
    - 'lengte_mm' naar numeriek
    - losse gat-kolommen => 'gaten_x@d_mm'
    - filter: alleen rijen met gaten
    """
    path = Path(path)
    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df = _clean_cols(df)
    df = df.dropna(how="all")

    # ffill voor basisvelden
    for c in ["profiel_naam", "profiel_type", "orientatie", "lengte_mm", "zijde"]:
        if c in df.columns:
            s = df[c].ffill()
            try:
                df[c] = s.infer_objects(copy=False)
            except Exception:
                df[c] = s

    # types
    if "lengte_mm" in df.columns:
        df["lengte_mm"] = pd.to_numeric(df["lengte_mm"], errors="coerce")

    # verwijder 'aantal'
    if "aantal" in df.columns:
        df = df.drop(columns=["aantal"])

    # combineer gaten en filter op rijen met gaten
    df = _combine_hole_columns(df)
    if "gaten_x@d_mm" in df.columns:
        has_holes = df["gaten_x@d_mm"].notna() & df["gaten_x@d_mm"].astype(str).str.strip().ne("")
        df = df[has_holes]

    # kolomvolgorde
    canonical = ["profiel_naam", "profiel_type", "orientatie", "lengte_mm", "zijde", "gaten_x@d_mm"]
    ordered = [c for c in canonical if c in df.columns] + [c for c in df.columns if c not in canonical]
    df = df[ordered]
    return df

# === Profielen bouwen (behoud ZIJKANT Yxx of T-slot A/B) ===
HOLE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*@\s*(\d+(?:\.\d+)?)\s*$")

def to_profiles(df: pd.DataFrame) -> list[ProfileSpec]:
    def map_side(z: str) -> str:
        u = " ".join(str(z).upper().split())
        # BOVENKANT
        if u.startswith("BOVENKANT"):
            return "BOVENKANT"
        # ZIJKANT Yxx (Y10, Y30, ...)
        m = re.search(r"ZIJKANT\s*Y\s*([0-9]+)", u) or re.search(r"ZIJKANT\s*Y([0-9]+)", u)
        if m:
            return f"ZIJKANT Y{m.group(1)}"
        # T-slot varianten (voor compat)
        if "ZIJKANT" in u and "B" in u:
            return "ZIJKANT T-slot B"
        if "ZIJKANT" in u and ("A" in u or "T-SLOT A" in u or "TSLOT A" in u):
            return "ZIJKANT T-slot A"
        # fallback
        if "ZIJKANT" in u:
            return "ZIJKANT Y10"
        return "BOVENKANT"

    profs: Dict[str, ProfileSpec] = {}
    for _, r in df.iterrows():
        name = str(r.get("profiel_naam", "")).strip() or "?"
        ptype = str(r.get("profiel_type", "")).strip()
        length = float(r.get("lengte_mm", 0) or 0)
        side = map_side(r.get("zijde", "BOVENKANT"))

        xs: List[float] = []
        s = r.get("gaten_x@d_mm", None)
        if pd.notna(s):
            for part in str(s).split("|"):
                m = HOLE_RE.match(part.strip())
                if m:
                    xs.append(float(m.group(1)))

        if name not in profs:
            profs[name] = ProfileSpec(name=name, ptype=ptype, length_mm=length, tool_diam=4.0, sections={})
        profs[name].sections.setdefault(side, []).extend(xs)
    return list(profs.values())

# Backwards-compat
def read_cutlist(path: Union[str, Path]) -> list[ProfileSpec]:
    df = load_excel(path)
    return to_profiles(df)
