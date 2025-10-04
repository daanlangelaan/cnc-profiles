from __future__ import annotations
import io, json, math, tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Optional, Dict, Any, List

import streamlit as st
import pandas as pd

# ---------------- project imports (met fallback) ----------------
try:
    from cncapp.excel_import import load_excel, to_profiles  # type: ignore
except Exception:
    load_excel = None
    to_profiles = None

try:
    from cncapp.gcode import generate_gcode  # type: ignore
except Exception:
    generate_gcode = None

# ---------------- pagina-setup ----------------
st.set_page_config(page_title="CNC Profiles", layout="wide")
st.title("🧩 CNC Profiles — Excel → Profiles → G-code")

# ---------------- helpers ----------------
@st.cache_data(show_spinner=False)
def _read_excel_bytes(b: bytes) -> pd.DataFrame:
    """Lees Excel uit upload (desnoods via fallback)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(b)
        tmp_path = Path(tmp.name)
    try:
        if load_excel:
            return load_excel(tmp_path)
        return pd.read_excel(io.BytesIO(b), sheet_name=0)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

@st.cache_data(show_spinner=False)
def _to_profiles_cached(df_json: str):
    """Cachebare wrapper om profielen te bouwen."""
    if to_profiles is None:
        return []
    df = pd.read_json(io.StringIO(df_json), orient="records")
    return to_profiles(df)

@st.cache_data(show_spinner=False)
def _gcode_cached(profiles_json: str, settings_json: str) -> str:
    """G-code cache: zet dicts om naar objecten en roep generate_gcode."""
    if generate_gcode is None:
        return ""
    settings = SimpleNamespace(**json.loads(settings_json))
    prof_dicts = json.loads(profiles_json)

    def to_obj(d: dict):
        ns = SimpleNamespace(**d)
        # sections: {str: list[float]}
        ns.sections = {k: [float(x) for x in (v or [])] for k, v in (ns.sections or {}).items()}
        return ns

    prof_objs = [to_obj(p) for p in prof_dicts]
    return generate_gcode(prof_objs, settings)

# ---- toolberekeningen (presets voor aluminium, HSS) ----
def rpm_from_surface_speed_mpm(V: float, D_mm: float) -> float:
    # n = (1000 * V) / (pi * D)
    return (1000.0 * float(V)) / (math.pi * max(0.01, float(D_mm)))

def feed_from_rev(n_rpm: float, f_rev_mm: float) -> float:
    return float(n_rpm) * float(f_rev_mm)

def safe_aluminum_presets() -> List[Dict[str, Any]]:
    """
    Veilige startwaarden voor HSS in aluminium.
    - Snijsnelheid V ≈ 80 m/min
    - Voeding per omw f_rev ≈ 0.02 + 0.01*D (mm/rev)
    Ø4.0 t/m Ø8.0 in stappen van 0.5 mm.
    """
    presets = []
    V = 80.0
    dia = 4.0
    while dia <= 8.0001:
        n = rpm_from_surface_speed_mpm(V, dia)           # rpm
        f_rev = 0.02 + 0.01 * dia                        # mm/rev
        plunge = feed_from_rev(n, f_rev)                 # mm/min
        presets.append({
            "name": f"Drill Ø{dia:.1f} HSS (Alu)",
            "diam_mm": round(dia, 1),
            "surface_mpm": V,
            "rpm": int(round(n)),
            "f_rev": round(f_rev, 3),
            "plunge_f": int(round(plunge)),
        })
        dia += 0.5
    return presets

# init tool-library in session
if "tool_library" not in st.session_state:
    st.session_state.tool_library = safe_aluminum_presets()

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("1) Excel")
    up = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
    use_sample = st.toggle("Gebruik sample_cutlist.xlsx", value=(up is None))

    st.header("2) Basis G-code")
    colA, colB = st.columns(2)
    with colA:
        work_offset = st.selectbox("Werkoffset", ["G54","G55","G56","G57","G58","G59"], index=0)
        safe_z = st.number_input("Safe Z", value=85.0, step=1.0)
        top_z  = st.number_input("Top Z",  value=0.0, step=0.5)
        depth  = st.number_input("Diepte (negatief boren)", value=-5.0, step=0.5)
    with colB:
        travel_f = st.number_input("Travel feed (mm/min)", value=6000.0, step=100.0)
        y10 = st.number_input("Y10", value=10.0, step=1.0)
        y30 = st.number_input("Y30", value=30.0, step=1.0)
        coolant_on = st.toggle("Koelmiddel (M8)", value=False)

    st.header("3) Tool-library")
    tabs = st.tabs(["Presets", "Custom / beheer"])

    # --- presets
    with tabs[0]:
        names = [t["name"] for t in st.session_state.tool_library]
        pick = st.selectbox("Kies preset", list(range(len(names))), format_func=lambda i: names[i])
        preset = st.session_state.tool_library[pick]
        st.caption("Alu-safe startwaarden (HSS). Pas gerust aan op eigen machine.")
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Ø (mm)", preset["diam_mm"])
        with col2: st.metric("RPM", preset["rpm"])
        with col3: st.metric("Plunge (mm/min)", preset["plunge_f"])

        # laat gebruiker alsnog bijstellen
        tool_diam = st.number_input("Ø Diameter tool (mm)", value=float(preset["diam_mm"]), step=0.1, min_value=0.1)
        spindle_rpm = st.number_input("Spindle RPM", value=int(preset["rpm"]), step=100, min_value=100)
        plunge_f = st.number_input("Plunge feed (mm/min)", value=int(preset["plunge_f"]), step=10, min_value=10)

    # --- custom / beheer
    with tabs[1]:
        st.write("Maak je eigen tool en voeg toe aan library.")
        c1, c2, c3 = st.columns(3)
        with c1:
            c_d = st.number_input("Ø Diameter (mm)", value=6.0, step=0.1, min_value=0.1, key="cust_d")
        with c2:
            c_v = st.number_input("Snijsnelheid V (m/min)", value=80.0, step=5.0, min_value=5.0, key="cust_v")
        with c3:
            c_frev = st.number_input("Voeding/omw f_rev (mm/rev)", value=0.08, step=0.01, min_value=0.01, key="cust_frev")
        c_rpm = int(round(rpm_from_surface_speed_mpm(c_v, c_d)))
        c_plunge = int(round(feed_from_rev(c_rpm, c_frev)))
        colx, coly, colz = st.columns(3)
        with colx: st.metric("RPM (calc)", c_rpm)
        with coly: st.metric("Plunge (calc)", c_plunge)
        with colz:
            if st.button("➕ Voeg toe"):
                st.session_state.tool_library.append({
                    "name": f"Drill Ø{c_d:.1f} custom",
                    "diam_mm": float(c_d),
                    "surface_mpm": float(c_v),
                    "rpm": int(c_rpm),
                    "f_rev": float(c_frev),
                    "plunge_f": int(c_plunge),
                })
                st.success("Tool toegevoegd aan library.")
        # export/import
        lib_json = json.dumps(st.session_state.tool_library, ensure_ascii=False, indent=2)
        st.download_button("⬇️ Exporteer library", lib_json, file_name="tool_library.json", mime="application/json")
        up_lib = st.file_uploader("Importeer library (JSON)", type=["json"], key="uplib")
        if up_lib is not None:
            try:
                st.session_state.tool_library = json.loads(up_lib.getvalue().decode("utf-8"))
                st.success("Library geïmporteerd.")
            except Exception as e:
                st.error(f"Import mislukt: {e}")

    st.header("4) Strategieën")
    c1, c2 = st.columns(2)
    with c1:
        peck_enable = st.checkbox("Peck drilling", value=False)
        peck_step = st.number_input("Peck stap (mm)", value=2.0, step=0.5, disabled=not peck_enable)
        peck_retract = st.number_input("Peck retract (mm)", value=1.0, step=0.5, disabled=not peck_enable)
        peck_dwell_ms = st.number_input("Peck dwell (ms)", value=0.0, step=50.0, disabled=not peck_enable)
    with c2:
        slow_start_enable = st.checkbox("Langzaam begin (eerste mm traag)", value=True)
        slow_start_mode = st.radio("Bereken N langzaam op basis van",
                                   ["factor × profiel-Z", "vast mm"],
                                   index=0, horizontal=False, disabled=not slow_start_enable)
        if slow_start_mode == "factor × profiel-Z":
            slow_start_factor = st.number_input("Factor (bijv. 0.4 → 40% van Z)", value=0.4, step=0.05,
                                                disabled=not slow_start_enable)
            slow_start_mm = 0.0
        else:
            slow_start_factor = 0.0
            slow_start_mm = st.number_input("Vaste mm (bijv. 4.0)", value=4.0, step=0.5,
                                            disabled=not slow_start_enable)
        slow_start_feed_mult = st.number_input("Feed-multiplier t.o.v. plunge", value=0.4, step=0.05,
                                               min_value=0.01, max_value=1.0, disabled=not slow_start_enable)

    st.header("5) Export")
    gext = st.selectbox("Bestandsextensie", [".nc", ".tap"], index=0)

# ---------------- DATA INLEZEN ----------------
df: Optional[pd.DataFrame] = None
if up is not None:
    df = _read_excel_bytes(up.getvalue())
elif use_sample and Path("sample_cutlist.xlsx").exists():
    df = _read_excel_bytes(Path("sample_cutlist.xlsx").read_bytes())

if df is None:
    st.info("⬅️ Upload een Excel of zet ‘Gebruik sample…’ aan.")
    st.stop()

st.success(f"Excel geladen — {len(df)} rijen, {df.shape[1]} kolommen")
st.dataframe(df.head(50), use_container_width=True)

# ---------------- PROFIELEN ----------------
if to_profiles is None:
    st.error("`to_profiles` ontbreekt. Controleer je projectimports.")
    st.stop()

profs = _to_profiles_cached(df.to_json(orient="records"))
# JSON-safe dump (werkt met pydantic/datataclasses/objects)
profs_json = json.dumps(
    [getattr(p, "model_dump", lambda: p)() if hasattr(p, "model_dump")
     else (p.dict() if hasattr(p, "dict") else getattr(p, "__dict__", p))
     for p in profs],
    ensure_ascii=False, indent=2
)

st.subheader("Profielen")
st.code(profs_json[:1200] + ("...\n" if len(profs_json) > 1200 else ""), language="json")
st.download_button("⬇️ Download profiles.json", profs_json, file_name="profiles.json", mime="application/json")

# ---------------- G-CODE ----------------
if generate_gcode is None:
    st.warning("`generate_gcode` niet gevonden; G-code export is uitgeschakeld.")
    st.stop()

# Stel settings samen → als JSON naar cache-fn
settings: Dict[str, Any] = {
    # basis
    "work_offset": work_offset,
    "safe_z": float(safe_z),
    "top_z": float(top_z),
    "depth": float(depth),
    "travel_f": float(travel_f),
    "coolant_on": bool(coolant_on),
    # tool
    "tool_diam": float(tool_diam),
    "spindle_rpm": int(spindle_rpm),
    "plunge_f": float(plunge_f),
    # Y-mapping
    "y_map": {"Y10": float(y10), "Y30": float(y30)},
    "y_top": 300.0, "y_slot_a": -10.0, "y_slot_b": 10.0,
    # peck
    "peck_enable": bool(peck_enable),
    "peck_step": float(peck_step),
    "peck_retract": float(peck_retract),
    "peck_dwell_ms": float(peck_dwell_ms),
    # langzaam begin (vanaf bovenzijde)
    "slow_start_enable": bool(slow_start_enable),
    "slow_start_mode": "factor" if slow_start_mode == "factor × profiel-Z" else "mm",
    "slow_start_factor": float(slow_start_factor),
    "slow_start_mm": float(slow_start_mm),
    "slow_start_feed_mult": float(slow_start_feed_mult),
    # .tap formatting
    "tap_mode": (gext == ".tap"),
}
settings_json = json.dumps(settings, ensure_ascii=False)

gcode = _gcode_cached(profs_json, settings_json)

st.subheader(f"G-code preview ({'TAP' if gext == '.tap' else 'NC'})")
st.code("\n".join(gcode.splitlines()[:220]), language="plaintext")
st.download_button(
    f"⬇️ Download cnc{gext}",
    gcode,
    file_name=f"cnc{gext}",
    mime="text/plain"
)

st.caption(
    f"Tool: Ø{tool_diam:.1f} mm • RPM {int(spindle_rpm)} • Plunge {int(plunge_f)} mm/min "
    f"• Peck={'aan' if peck_enable else 'uit'} • Langzaam begin={'aan' if slow_start_enable else 'uit'}"
)
