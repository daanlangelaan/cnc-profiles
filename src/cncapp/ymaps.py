from typing import Tuple

def ymap(ptype: str) -> Tuple[float, float]:
    """Return (topY, sideY) for given profile type.
       SideY = Y=10 (zij-A), Y=30 (zij-B) regelen we bij aanroep."""
    p = ptype.lower().replace("x", "x").strip()
    spec = {
        "20x20": (10.0, 10.0),
        "20x40": (10.0, 10.0),
        "30x30": (15.0, 15.0),
        "40x40": (20.0, 20.0),
        "40x80": (20.0, 20.0),
    }
    return spec.get(p, (10.0, 10.0))
