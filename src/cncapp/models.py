from typing import Literal, List, Dict
from pydantic import BaseModel

Side = Literal["BOVENKANT", "ZIJKANT T-slot A", "ZIJKANT T-slot B"]

class ProfileSpec(BaseModel):
    name: str           # bv. "Profiel 3"
    ptype: str          # bv. "20x40"
    length_mm: float
    tool_diam: float    # bv. 4.0
    sections: Dict[Side, List[float]]  # X-posities per zijde (mm)

class Settings(BaseModel):
    slow_approach: float = 2.0      # mm langzaam aanboren
    peck_step: float = 3.0          # mm per peck
    peck_retract: float = 0.5       # mm terug
    z_safe: float = 85.0            # jouw wens
    z_clear: float = 55.0
    final_depth: float = -2.0       # eind Z (onderkant)
    spindle_rpm: int = 11000
    feed_drill: int = 250
    feed_approach: int = 100
