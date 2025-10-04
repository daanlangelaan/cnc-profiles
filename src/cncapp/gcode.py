from __future__ import annotations
from typing import Iterable, List, Dict, Optional
import math, re

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

# ------------- helpers -------------

def _fmt(x: float, tap: bool=False) -> str:
    return f"{float(x):.1f}" if tap else f"{float(x):.3f}"

def _fmt_i(x: float | int) -> str:
    return str(int(round(float(x))))

def _get(settings: Optional[Settings], attr: str, default):
    return getattr(settings, attr, default) if settings is not None else default

def _side_to_y(side: str, settings: Optional[Settings]) -> Optional[float]:
    u = " ".join(str(side).upper().split())
    y_map: Dict[str, float] = _get(settings, "y_map", {"Y10": 10.0, "Y30": 30.0})
    if u.startswith("BOVENKANT"):
        return float(_get(settings, "y_top", 300.0))
    if "ZIJKANT" in u and "T-SLOT A" in u:
        return float(_get(settings, "y_slot_a", -10.0))
    if "ZIJKANT" in u and "T-SLOT B" in u:
        return float(_get(settings, "y_slot_b", 10.0))
    for key, val in y_map.items():
        if f"ZIJKANT {key}" in u:
            return float(val)
    return None

_DIM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)", re.I)
def _profile_thickness(ptype: str, fallback: float = 20.0) -> float:
    m = _DIM_RE.search(str(ptype))
    if not m:
        return float(fallback)
    a, b = float(m.group(1)), float(m.group(2))
    return float(min(a, b))

# ------------- hoofd API -------------

def generate_gcode(profiles: Iterable[ProfileSpec], settings: Optional[Settings] = None) -> str:
    """
    Boor-G-code met:
      • Peck drilling
      • Langzaam begin (eerste N mm langzaam: factor×Z of vast mm)
    Plus .tap modus (preamble/homing/format).

    Settings (selectie):
      work_offset=G54, safe_z=85, top_z=0, depth=-5, travel_f=6000, plunge_f=300
      spindle_rpm=5000, tool_diam=4.0, coolant_on=False
      peck_enable, peck_step, peck_retract, peck_dwell_ms
      slow_start_enable, slow_start_mode('factor'|'mm'), slow_start_factor, slow_start_mm, slow_start_feed_mult
      tap_mode=False
    """
    profiles = list(profiles)
    tap = bool(_get(settings, "tap_mode", False))

    work_offset = str(_get(settings, "work_offset", "G54"))
    safe_z     = float(_get(settings, "safe_z", 85.0))
    top_z      = float(_get(settings, "top_z", 0.0))
    depth      = float(_get(settings, "depth", -5.0))    # negatief is boren
    plunge_f   = float(_get(settings, "plunge_f", 300.0))
    travel_f   = float(_get(settings, "travel_f", 6000.0))

    tool_diam   = float(_get(settings, "tool_diam", 4.0))
    spindle_rpm = float(_get(settings, "spindle_rpm", 5000.0))
    coolant_on  = bool(_get(settings, "coolant_on", False))

    peck_enable   = bool(_get(settings, "peck_enable", False))
    peck_step     = abs(float(_get(settings, "peck_step", 2.0)))
    peck_retract  = abs(float(_get(settings, "peck_retract", 1.0)))
    peck_dwell_ms = max(0.0, float(_get(settings, "peck_dwell_ms", 0.0)))

    slow_start_enable     = bool(_get(settings, "slow_start_enable", False))
    slow_start_mode       = str(_get(settings, "slow_start_mode", "factor")).lower()
    slow_start_factor     = float(_get(settings, "slow_start_factor", 0.4))
    slow_start_mm_fixed   = abs(float(_get(settings, "slow_start_mm", 4.0)))
    slow_start_feed_mult  = max(0.01, float(_get(settings, "slow_start_feed_mult", 0.4)))
    slow_feed             = float(plunge_f * slow_start_feed_mult)

    target_z = top_z + depth

    def drill_moves_for_one_hole(ptype: str) -> List[str]:
        lines: List[str] = []

        # langzaam begin
        start_mm = 0.0
        if slow_start_enable:
            if slow_start_mode == "factor":
                start_mm = slow_start_factor * _profile_thickness(ptype, fallback=20.0)
            else:
                start_mm = slow_start_mm_fixed
        total_depth_mm = abs(target_z - top_z)
        start_mm = min(max(0.0, start_mm), total_depth_mm)

        current = top_z
        if start_mm > 0:
            slow_target = max(target_z, top_z - start_mm)
            lines.append(f"G1 Z{_fmt(slow_target, tap)} F{_fmt(slow_feed, tap)}")
            current = slow_target

        if peck_enable:
            if current <= target_z + 1e-6:
                lines.append(f"G0 Z{_fmt(safe_z, tap)}")
                return lines
            remaining = abs(current - target_z)
            n = max(1, math.ceil(remaining / peck_step))
            for _ in range(n):
                next_z = max(target_z, current - peck_step)
                lines.append(f"G1 Z{_fmt(next_z, tap)} F{_fmt(plunge_f, tap)}")
                current = next_z
                if current > target_z:
                    lines.append(f"G0 Z{_fmt(min(top_z, current + peck_retract), tap)}")
                    if peck_dwell_ms > 0:
                        lines.append(f"G4 P{peck_dwell_ms/1000.0:.3f}")
            lines.append(f"G0 Z{_fmt(safe_z, tap)}")
            return lines

        if current > target_z:
            lines.append(f"G1 Z{_fmt(target_z, tap)} F{_fmt(plunge_f, tap)}")
        lines.append(f"G0 Z{_fmt(safe_z, tap)}")
        return lines

    lines: List[str] = []

    if tap:
        # TAP preamble (zoals je voorbeeld)
        first = profiles[0] if profiles else None
        title = f"({getattr(first,'name','Program')}  {getattr(first,'ptype','')} L={getattr(first,'length_mm','')} mm)"
        lines += [
            title,
            "G90 G94 G91.1 G40 G49 G17",
            "G21",
            "G28 G91 Z0.",
            "G90",
            work_offset,
            f"S{_fmt_i(spindle_rpm)} M3",
        ]
        if coolant_on:
            lines.append("M8")
        lines.append(f"G0 Z{_fmt(safe_z, tap)}")
    else:
        # oude .nc header
        lines += [
            "(G-CODE)",
            "G90 G21",
            "G17",
            work_offset,
            f"(TOOL DRILL D{_fmt(tool_diam) }mm)",
            f"S{_fmt_i(spindle_rpm)} M3",
        ]
        if coolant_on:
            lines.append("M8")
        lines.append(f"G0 Z{_fmt(safe_z)}")

    for idx, p in enumerate(profiles, start=1):
        name   = getattr(p, "name", f"PROFILE_{idx}")
        ptype  = getattr(p, "ptype", "")
        length = getattr(p, "length_mm", "")

        lines.append(f"(PROFILE {name} {ptype} L{length})")
        lines.append("G0 X0.000" if not tap else "G0 X0.")
        lines.append(f"G0 Z{_fmt(safe_z, tap)}")
        lines.append("G0 Y300.000" if not tap else "G0 Y300.")

        sections = getattr(p, "sections", {}) or {}

        for side, xs in sections.items():
            y = _side_to_y(side, settings)
            if y is None:
                lines.append(f"(SKIP onbekende zijde: {side})")
                continue

            # comment zoals jouw .tap sample (met Y)
            u = str(side).upper()
            if u.startswith("ZIJKANT"):
                lines.append(f"(ZIJKANT {u.split()[-1]} Y={_fmt(y, tap)})")
            else:
                lines.append(f"({side})")

            # naar Y en boorgaten
            lines.append(f"G0 Y{_fmt(y, tap)}" if tap else f"G0 Y{_fmt(y)} F{_fmt(travel_f)}")
            for x in xs or []:
                try:
                    xf = float(x)
                except Exception:
                    continue
                lines.append(f"G0 X{_fmt(xf, tap)}" if tap else f"G0 X{_fmt(xf)} F{_fmt(travel_f)}")
                lines += drill_moves_for_one_hole(ptype)

    # afsluiting
    if tap:
        if coolant_on:
            lines.append("M9")
        lines += [
            "M5",
            "G28 G91 Z0.",
            "G90",
            "G28 G91 X0. Y0.",
            "G90",
            "M30",
        ]
    else:
        lines.append("M30")

    return "\n".join(lines)
