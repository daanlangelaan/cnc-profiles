import pandas as pd
from .models import ProfileSpec

# Verwachte kolommen (kunnen we later flexibel maken):
# id, ptype, length_mm, side, positions (komma-gescheiden x)
def read_cutlist(path: str) -> list[ProfileSpec]:
    df = pd.read_excel(path)
    # normaliseer
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    profs: dict[str, ProfileSpec] = {}
    for _, r in df.iterrows():
        pid = str(r["id"])
        ptype = str(r["ptype"])
        length = float(r["length_mm"])
        side = str(r["side"]).strip().upper()
        xs = [float(x) for x in str(r["positions"]).replace(";", ",").split(",") if str(x).strip()]
        if pid not in profs:
            profs[pid] = ProfileSpec(
                name=f"Profiel {pid}", ptype=ptype, length_mm=length,
                tool_diam=4.0, sections={}
            )
        prof = profs[pid]
        prof.sections.setdefault(side, []).extend(xs)
    return list(profs.values())
