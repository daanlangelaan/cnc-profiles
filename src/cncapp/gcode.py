from .models import Settings

HEADER = """(PROJECT: cutlist)
G90 G94 G91.1 G40 G49 G17
G21
G28 G91 Z0.
G90
"""

FOOTER = """M9
M5
G28 G91 Z0.
G90
G28 G91 X0. Y0.
G90
M30
"""

def safe_moves_order(settings: Settings) -> list[str]:
    # Altijd X0 -> Z85 -> Y300 (zoals jij vroeg)
    return [ "G0 X0.000",
             f"G0 Z{settings.z_safe:.3f}",
             "G0 Y300.000" ]

def start_spindle(settings: Settings) -> list[str]:
    return [f"S{settings.spindle_rpm} M3"]

def stop_spindle() -> list[str]:
    return ["M5"]
