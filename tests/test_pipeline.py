from cncapp.models import ProfileSpec, Settings
from cncapp.pipeline import build_program

def test_build_contains_side_blocks():
    p = ProfileSpec(
        name="Profiel 1", ptype="20x40", length_mm=1000, tool_diam=4.0,
        sections={
            "BOVENKANT": [10.0],
            "ZIJKANT T-slot A": [50.0],
            "ZIJKANT T-slot B": [60.0],
        }
    )
    g = build_program([p], Settings())
    assert "(PLAATS PROFIEL: Profiel 1   ZIJKANT A)" in g
    assert "(PLAATS PROFIEL: Profiel 1   ZIJKANT B)" in g
    assert "(PLAATS PROFIEL: Profiel 1   BOVENKANT)" in g
    assert "G0 X0.000" in g and "G0 Z85.000" in g and "G0 Y300.000" in g
