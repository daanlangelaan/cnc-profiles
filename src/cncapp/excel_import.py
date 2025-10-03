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
    "aantal": "aantal",
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
    # bundel alle kolommen met '@' in 'gaten_x@d_mm'
    if "gaten_x@d_mm" not in df.columns:
        df["gaten_x@d_mm"] = None
    hole_cols: List[str] = [c for c in df.columns if c == "gaten_x@d_mm"]
    for c in df.columns:
        if c == "gaten_x@d_mm":
            continue
        try:
            if df[c].astype(str).str.contains("@", na=False).any():
                hole_cols.append(c)
        except Exception:
            continue

    if len(hole_cols) > 1:
        def join_row(row):
            parts = []
            for c in hole_cols:
                v = row.get(c, None)
                if pd.notna(v):
                    s = str(v).strip()
                    if s and s != "nan":
                        parts.append(s)
            return " | ".join(parts) if parts else None

        df["gaten_x@d_mm"] = df[hole_cols].apply(join_row, axis=1)
        df = df.drop(columns=[c for c in hole_cols if c != "gaten_x@d_mm"])
    return df

def load_excel(path: Union[str, Path]) -> pd.DataFrame:
    """
    Lees jouw Excel (zoals in de screenshots) in en maak 'm analyse-klaar:
    - 1 rij per 'zijde'
    - forward-fill van profiel_naam / type / oriëntatie / lengte_mm / aantal
    - zet lengte_mm & aantal naar numeriek
    - bundel losse gat-kolommen in 'gaten_x@d_mm'
    - verwijder volledig lege Unnamed-kolommen
    """
    path = Path(path)
    df = pd.read_excel(path, sheet_name=0, dtype=object)
    df = _clean_cols(df)
    df = df.dropna(how="all")

    # vul lege vervolgregels aan met vorige waarden
    keys = ["profiel_naam", "profiel_type", "orientatie", "lengte_mm", "aantal"]
    for c in keys:
        if c in df.columns:
            df[c] = df[c].ffill()

    # normaliseer types
    if "lengte_mm" in df.columns:
        df["lengte_mm"] = pd.to_numeric(df["lengte_mm"], errors="coerce")
    if "aantal" in df.columns:
        df["aantal"] = pd.to_numeric(df["aantal"], errors="coerce")

    if "zijde" in df.columns:
        df["zijde"] = df["zijde"].astype(str).str.strip()
        df.loc[df["zijde"].isin(["", "nan", "None"]), "zijde"] = pd.NA

    df = _combine_hole_columns(df)

    # kolomvolgorde
    canonical = ["profiel_naam","profiel_type","orientatie","lengte_mm","aantal","zijde","gaten_x@d_mm"]
    ordered = [c for c in canonical if c in df.columns] + [c for c in df.columns if c not in canonical]
    df = df[ordered]
    return df

# === Optioneel: converter naar ProfileSpec (voor gcode e.d.) ===
HOLE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*@\s*(\d+(?:\.\d+)?)\s*$")

def to_profiles(df: pd.DataFrame) -> list[ProfileSpec]:
    def map_side(z: str) -> str:
        z = str(z).upper()
        if z.startswith("BOVENKANT"):
            return "BOVENKANT"
        if "ZIJKANT" in z:
            return "ZIJKANT T-slot A"
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
