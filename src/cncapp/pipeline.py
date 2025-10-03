from typing import Iterable
from .models import ProfileSpec, Settings
from .ymaps import ymap
from .gcode import HEADER, FOOTER, safe_moves_order, start_spindle, stop_spindle
from .strategies import slow_then_peck

def drill_block(side_label: str, y: float, xs: Iterable[float], settings: Settings) -> list[str]:
    g = []
    if not xs:
        return g
    g += [f"({side_label} - Y={y:.1f})",
          f"G0 Z{settings.z_clear:.3f}"]
    for x in xs:
        g += [f"G0 X{x:.3f} Y{y:.3f}"]
        g += slow_then_peck(
            z_from=settings.z_clear-10, z_to=settings.final_depth, z_clear=settings.z_clear,
            feed_approach=settings.feed_approach, feed_drill=settings.feed_drill,
            peck_step=settings.peck_step, peck_retract=settings.peck_retract
        )
    return g

def make_gcode_for_profile(p: ProfileSpec, settings: Settings, idx: int) -> list[str]:
    topY, sideY = ymap(p.ptype)
    xa = p.sections.get("ZIJKANT T-slot A", []) or p.sections.get("ZIJKANT", [])
    xb = p.sections.get("ZIJKANT T-slot B", [])
    xt = p.sections.get("BOVENKANT", [])

    g = []
    # Startblok + veilige verplaatsingen
    g += safe_moves_order(settings)
    g += safe_moves_order(settings)   # vaak gewenst in je output
    g += [f"M0 (PLAATS PROFIEL: {p.name}   START OP ZIJKANT)",
          f"(START PROFIEL {p.name}   {p.ptype}  L={p.length_mm:.1f} mm  Tool=Boor  {p.tool_diam:.1f})",
          f"G0 Z{settings.z_clear:.3f}"]

    # ZIJKANTEN (indien aanwezig)
    g += stop_spindle()
    g += safe_moves_order(settings)
    g += ["(<<< DRAAI PROFIEL MANUEEL NAAR ZIJKANT >>>)"]
    g += start_spindle(settings)
    g += [f"G0 Z{settings.z_clear:.3f}"]

    # Side A (Y=10)
    if xa:
        g += safe_moves_order(settings)
        g += [f"M0 (PLAATS PROFIEL: {p.name}   ZIJKANT A)"]
        g += drill_block("ZIJKANT - Y10", y=sideY, xs=xa, settings=settings)

    # Side B (Y=30) — geforceerd 30, onafhankelijk van sideY
    if xb:
        g += safe_moves_order(settings)
        g += [f"M0 (PLAATS PROFIEL: {p.name}   ZIJKANT B)"]
        g += drill_block("ZIJKANT - Y30", y=30.0, xs=xb, settings=settings)

    # BOVENKANT
    g += stop_spindle()
    g += safe_moves_order(settings)
    g += ["(<<< DRAAI PROFIEL MANUEEL NAAR BOVENKANT >>>)"]
    g += start_spindle(settings)
    g += [f"G0 Z{settings.z_clear:.3f}",
          *safe_moves_order(settings),
          f"M0 (PLAATS PROFIEL: {p.name}   BOVENKANT)"]
    g += drill_block("BOVENKANT", y=topY, xs=xt, settings=settings)

    g += stop_spindle()
    g += [f"(EINDE PROFIEL {p.name})"]
    g += safe_moves_order(settings)
    return g

def build_program(profiles: Iterable[ProfileSpec], settings: Settings) -> str:
    lines = [HEADER, *start_spindle(settings)]
    for i, p in enumerate(profiles, start=1):
        lines += make_gcode_for_profile(p, settings, i)
    lines += [FOOTER]
    return "\n".join(lines)
