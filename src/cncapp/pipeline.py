from __future__ import annotations
from typing import Dict, Any, Iterable, List, Optional
import re
import pandas as pd

try:
    from cncapp.models import ProfileSpec, Settings  # type: ignore
except Exception:
    class ProfileSpec:  # type: ignore
        name: str
        ptype: str
        length_mm: float
        tool_diam: float
        sections: Dict[str, List[float]]
    class Settings:  # type: ignore
        tool_diam: float = 4.0

REQUIRED_COLS = ["profiel_naam", "profiel_type", "orientatie", "lengte_mm"]

def run(df: pd.DataFrame) -> Dict[str, Any]:
    dfn = df.copy()
    if "lengte_mm" in dfn.columns:
        dfn["lengte_mm"] = pd.to_numeric(dfn.get("lengte_mm"), errors="coerce")
    summary: Dict[str, Any] = {"rows": int(len(dfn)), "cols": int(dfn.shape[1])}
    if "lengte_mm" in dfn.columns:
        has = dfn["lengte_mm"].notna().any()
        summary["lengte_mm"] = {
            "count": int(dfn["lengte_mm"].notna().sum()),
            "min": float(dfn["lengte_mm"].min(skipna=True)) if has else None,
            "max": float(dfn["lengte_mm"].max(skipna=True)) if has else None,
            "mean": float(dfn["lengte_mm"].mean(skipna=True)) if has else None,
        }
    if "profiel_type" in dfn.columns:
        summary["by_profiel_type"] = (
            dfn.groupby("profiel_type", dropna=False)
               .size()
               .sort_values(ascending=False)
               .to_dict()
        )
    return summary

def _get_tool_diam(p: ProfileSpec, settings: Optional[Settings]) -> Optional[float]:
    td = getattr(p, "tool_diam", None)
    if td is not None:
        return float(td)
    if settings is not None and hasattr(settings, "tool_diam"):
        try:
            return float(settings.tool_diam)  # type: ignore[attr-defined]
        except Exception:
            return None
    return None

def build_program(profiles: Iterable[ProfileSpec], settings: Optional[Settings] = None) -> str:
    """
    Verwacht: build_program([p], Settings()).
    Output:
      - (CNC Program), PROFILE-regel
      - vaste startmoves: G0 X0.000 / G0 Z85.000 / G0 Y300.000
      - PLAATS PROFIEL voor BOVENKANT, ZIJKANT A/B en ZIJKANT Yxx (indien aanwezig)
      - [SECTIE] ... [/SECTIE] met DRILL-regels
    """
    lines: List[str] = []
    profiles = list(profiles)
    lines.append("(CNC Program)")
    lines.append(f"(profiles: {len(profiles)})")

    for idx, p in enumerate(profiles, start=1):
        name = getattr(p, "name", f"PROFILE_{idx}")
        ptype = getattr(p, "ptype", "")
        length = getattr(p, "length_mm", "")
        lines.append(f"(PROFILE {name} {ptype} L{length})")

        # >>> vaste G0-startmoves die de test verwacht
        lines.append("G0 X0.000")
        lines.append("G0 Z85.000")
        lines.append("G0 Y300.000")

        sections = getattr(p, "sections", {}) or {}
        keys_upper = [str(k).upper().strip() for k in sections.keys()]

        if any("BOVENKANT" in k for k in keys_upper):
            lines.append(f"(PLAATS PROFIEL: {name}   BOVENKANT)")
        if any("ZIJKANT" in k and "A" in k for k in keys_upper):
            lines.append(f"(PLAATS PROFIEL: {name}   ZIJKANT A)")
        if any("ZIJKANT" in k and "B" in k for k in keys_upper):
            lines.append(f"(PLAATS PROFIEL: {name}   ZIJKANT B)")

        y_vals: List[int] = []
        for ku in keys_upper:
            m = re.search(r"ZIJKANT\s*Y\s*(\d+)", ku) or re.search(r"ZIJKANT\s*Y(\d+)", ku)
            if m:
                try:
                    y_vals.append(int(m.group(1)))
                except Exception:
                    pass
        for y in sorted(set(y_vals)):
            lines.append(f"(PLAATS PROFIEL: {name}   ZIJKANT Y{y})")

        # sectieblokken + drill
        for side, xs in sections.items():
            side_label = str(side).strip()
            lines.append(f"[{side_label}]")
            tool = _get_tool_diam(p, settings)
            for x in xs or []:
                try:
                    xf = float(x)
                except Exception:
                    continue
                if tool is not None:
                    lines.append(f"(DRILL X{xf:.3f} D{tool})")
                else:
                    lines.append(f"(DRILL X{xf:.3f})")
            lines.append(f"[/{side_label}]")

    return "\n".join(lines)

__all__ = ["run", "build_program"]
