"""
app.py - the interface for the rocket engine sizing tool.

Start it from the Terminal (inside the rocket-sizing folder, with .venv active):

    streamlit run app.py

or double-click "Start Rocket Sizing Tool.command".

All of the engineering math lives in engine.py; this file only collects the
inputs and displays the results in a blueprint style.
"""

import datetime
import io
import logging

import matplotlib
matplotlib.use("Agg")
logging.getLogger("matplotlib").setLevel(logging.ERROR)
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle
import numpy as np
import pandas as pd
import streamlit as st

import engine
from engine import Inputs, size_engine, contour, sweep, composition

# ---------------------------------------------------------------------------
# Your name: appears in the title block, the watermark and the page footer.
# ---------------------------------------------------------------------------
AUTHOR = "Yahshua Nazareth"
DRAWING_TITLE = "LIQUID ROCKET THRUST CHAMBER"

# Blueprint palette
BG = "#0b3866"       # blueprint blue
PANEL = "#0f4580"
WHITE = "#ffffff"
SOFT = "#cfe3ff"     # secondary text
CYAN = "#8fd0ff"     # second data series, centerlines
FAINT = (1, 1, 1, 0.10)

plt.rcParams.update({
    "font.family": "monospace",
    "font.monospace": ["DejaVu Sans Mono", "Menlo", "Courier New"],
    "font.size": 9,
    "text.color": WHITE,
    "axes.facecolor": BG,
    "figure.facecolor": BG,
    "savefig.facecolor": BG,
    "axes.edgecolor": SOFT,
    "axes.labelcolor": SOFT,
    "xtick.color": SOFT,
    "ytick.color": SOFT,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "hatch.color": WHITE,
    "hatch.linewidth": 0.5,
})

st.set_page_config(page_title="Rocket Engine Sizing Tool", page_icon="🚀",
                   layout="wide")

st.markdown(f"""
<style>
.stApp {{
  background-color: {BG};
  background-image:
    linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
  background-size: 24px 24px;
}}
h1, h2, h3, h4 {{ font-family: monospace !important; letter-spacing: 0.04em; }}
[data-testid="stMetric"] {{
  border: 1px solid rgba(255,255,255,0.55);
  padding: 10px 14px 8px 14px;
  background: rgba(11,56,102,0.85);
}}
[data-testid="stMetricLabel"] p {{
  font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: {SOFT};
}}
[data-testid="stMetricValue"] {{ font-size: 1.55rem; }}
.bp-watermark {{
  position: fixed; right: 18px; bottom: 10px; z-index: 1000;
  font-family: monospace; font-size: 0.75rem; letter-spacing: 0.12em;
  color: rgba(255,255,255,0.45); pointer-events: none;
}}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none; }}
.bp-sub {{ font-family: monospace; color: {SOFT}; font-size: 0.85rem;
           letter-spacing: 0.06em; }}
</style>
<div class="bp-watermark">PROGRAM BY {AUTHOR.upper()}</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cached wrappers: Streamlit re-runs this whole file whenever a slider moves,
# so we remember earlier answers instead of calling NASA CEA again.
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cached_size(settings: tuple):
    return size_engine(Inputs(**dict(settings)))


@st.cache_data(show_spinner=False)
def cached_sweep(settings: tuple, name: str, values: tuple):
    return sweep(Inputs(**dict(settings)), name, values)


@st.cache_data(show_spinner=False)
def cached_composition(settings: tuple):
    return composition(Inputs(**dict(settings)))


# ---------------------------------------------------------------------------
# Sidebar: the design choices
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("DESIGN INPUTS")

    st.subheader("Propellants")
    ox_label = st.selectbox("Oxidizer", list(engine.OXIDIZERS))
    fuel_label = st.selectbox("Fuel", list(engine.FUELS))
    ox = engine.OXIDIZERS[ox_label]
    fuel = engine.FUELS[fuel_label]

    st.subheader("Performance")
    thrust = st.number_input("Target thrust (lbf)", 10.0, 100000.0, 500.0,
                             step=50.0)
    basis = st.radio("Thrust is measured", ["In vacuum", "At sea level"],
                     horizontal=True,
                     help="Air pressure pushes back on the exhaust, so the "
                          "same engine makes less thrust at sea level.")
    Pc = st.slider("Chamber pressure Pc (psia)", 100, 1500, 300, step=10,
                   help="Small pressure-fed engines usually run 150-500 psia.")
    MR = st.slider("Mixture ratio O/F (by mass)", 0.5, 12.0,
                   engine.DEFAULT_MR[(ox, fuel)], step=0.1,
                   key=f"MR-{ox}-{fuel}")   # resets when propellants change
    eps = st.slider("Expansion ratio ε = Ae/At", 2.0, 100.0, 8.0, step=0.5)

    st.subheader("Geometry")
    contraction_ratio = st.slider("Contraction ratio Ac/At", 2.0, 12.0, 6.0,
                                  step=0.5, help="Typical range is 4 to 8.")
    Lstar = st.slider("Characteristic length L* (in)", 20, 80, 40, step=1,
                      help="Chamber volume / throat area. Longer gives the "
                           "propellants more time to burn.")
    half_angle = st.slider("Nozzle half-angle α (deg)", 10, 20, 15,
                           help="15° is the classic conical nozzle.")
    conv_angle = st.slider("Converging half-angle β (deg)", 20, 45, 30)

    st.caption(f"Rocket Engine Sizing Tool · {AUTHOR}")

inp = Inputs(ox=ox, fuel=fuel, thrust=thrust, Pc=float(Pc), MR=MR, eps=eps,
             thrust_at_sea_level=(basis == "At sea level"),
             contraction_ratio=contraction_ratio, Lstar=float(Lstar),
             half_angle=float(half_angle), conv_angle=float(conv_angle))
settings = tuple(sorted(inp.__dict__.items()))

try:
    res = cached_size(settings)
except Exception as err:
    st.error("NASA CEA could not find a solution for these inputs. "
             f"Try a different mixture ratio or pressure. ({err})")
    st.stop()

TODAY = datetime.date.today().strftime("%Y-%m-%d").upper()
DWG_NO = f"RES-{ox}-{fuel}-{int(round(thrust))}".upper()


# ---------------------------------------------------------------------------
# Header and headline numbers
# ---------------------------------------------------------------------------
st.title("ROCKET ENGINE SIZING TOOL")
st.markdown(
    f'<div class="bp-sub">{ox_label.upper()} / {fuel_label.upper()} · '
    f'{thrust:,.0f} LBF {basis.upper()} · DWG {DWG_NO} · '
    f'THERMOCHEMISTRY: NASA CEA · {AUTHOR.upper()}</div>',
    unsafe_allow_html=True)
st.write("")

row1 = st.columns(5)
row1[0].metric("Isp vacuum", f"{res.Isp_vac:.1f} s")
row1[1].metric("Isp sea level", f"{res.Isp_sl:.1f} s")
row1[2].metric("c* (char. velocity)", f"{res.cstar:,.0f} ft/s")
row1[3].metric("Cf vacuum", f"{res.Cf_vac:.3f}")
row1[4].metric("Chamber temp Tc", f"{res.Tc:,.0f} °R")

row2 = st.columns(5)
row2[0].metric("Mass flow ṁ", f"{res.mdot:.3f} lb/s")
row2[1].metric("Throat Ø", f"{res.Dt:.3f} in")
row2[2].metric("Exit Ø", f"{res.De:.3f} in")
row2[3].metric("Exit Mach", f"{res.M_exit:.2f}")
row2[4].metric("Overall length", f"{res.L_total:.2f} in")

if res.sl_condition.startswith("Separated"):
    st.warning("At sea level the exhaust would separate from the nozzle wall "
               f"(exit pressure {res.Pe:.1f} psia is far below 14.7). "
               "This expansion ratio only suits high altitude or vacuum. "
               f"The sea-level optimum is ε ≈ {res.eps_optimum:.1f}.")


# ---------------------------------------------------------------------------
# The engineering drawing
# ---------------------------------------------------------------------------
def dim_line(ax, p1, p2, text, offset=(0, 0), ha="center", va="center",
             rotation=0):
    ax.annotate("", p2, p1, arrowprops=dict(arrowstyle="<|-|>", color=WHITE,
                                            lw=0.8, mutation_scale=7))
    mx, my = (p1[0] + p2[0]) / 2 + offset[0], (p1[1] + p2[1]) / 2 + offset[1]
    ax.text(mx, my, text, ha=ha, va=va, fontsize=8.5, rotation=rotation,
            bbox=dict(facecolor=BG, edgecolor="none", pad=1.2))


def draw_blueprint(res, inp):
    pts = contour(res)
    xs = np.array([p[0] for p in pts])
    rs = np.array([p[1] for p in pts])
    L = xs[-1]
    wall = 0.08 * res.Dc + 0.06
    R = rs.max() + wall

    fig = plt.figure(figsize=(14, 9))

    # Background sheet: grid and border
    bg = fig.add_axes([0, 0, 1, 1])
    bg.set_xlim(0, 1); bg.set_ylim(0, 1); bg.axis("off")
    for g in np.arange(0, 1.0001, 0.02):
        bg.axvline(g, color=FAINT, lw=0.4)
        bg.axhline(g, color=FAINT, lw=0.4)
    bg.add_patch(Rectangle((0.012, 0.015), 0.976, 0.97, fill=False,
                           ec=WHITE, lw=1.6))
    bg.add_patch(Rectangle((0.018, 0.024), 0.964, 0.952, fill=False,
                           ec=WHITE, lw=0.5))
    bg.text(0.5, 0.56, AUTHOR.upper(), ha="center", va="center",
            fontsize=74, color=(1, 1, 1, 0.055), rotation=18,
            fontweight="bold")

    # Main view
    ax = fig.add_axes([0.05, 0.36, 0.90, 0.58])
    ax.set_facecolor("none")
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")

    # Walls (hatched section) and injector plate
    for s in (1, -1):
        outer = [(x, s * (r + wall)) for x, r in zip(xs, rs)]
        inner = [(x, s * r) for x, r in zip(xs, rs)]
        ax.add_patch(Polygon(inner + outer[::-1], closed=True, fc=BG,
                             ec=WHITE, lw=1.3, hatch="////"))
    ax.add_patch(Rectangle((-wall * 1.6, -(rs[0] + wall)), wall * 1.6,
                           2 * (rs[0] + wall), fc=BG, ec=WHITE, lw=1.3,
                           hatch="xxxx"))

    # Centerline
    ax.plot([-0.06 * L, 1.04 * L], [0, 0], color=CYAN, lw=0.8,
            linestyle=(0, (14, 3, 2, 3)))
    ax.text(1.045 * L, 0, "CL", color=CYAN, fontsize=8, va="center")

    # Flow arrow
    ax.annotate("", (0.30 * xs[1], 0.0), (0.06 * xs[1], 0.0),
                arrowprops=dict(arrowstyle="-|>", color=CYAN, lw=1.2))
    ax.text(0.18 * xs[1], 0.10 * rs[0], "FLOW", color=CYAN, ha="center",
            fontsize=8)

    # Stations
    names = ["", "STA 1\nCHAMBER", "STA 2\nTHROAT", "STA 3\nEXIT"]
    for x, name in zip(xs[1:], names[1:]):
        ax.plot([x, x], [-R * 1.05, R * 1.25], color=SOFT, lw=0.6,
                linestyle=(0, (4, 3)))
        ax.text(x, R * 1.32, name, ha="center", va="bottom", fontsize=8,
                color=SOFT, linespacing=1.1)
    ax.text(0, R * 1.32, "INJECTOR\nFACE", ha="center", va="bottom",
            fontsize=8, color=SOFT, linespacing=1.1)

    # Diameters
    dim_line(ax, (0.62 * xs[1], -rs[0]), (0.62 * xs[1], rs[0]),
             f"Ø{res.Dc:.3f}", offset=(0, 0.45 * rs[0]))
    dim_line(ax, (xs[2], -rs[2]), (xs[2], rs[2]), f"Ø{res.Dt:.3f}",
             offset=(0.035 * L, 0), ha="left")
    dim_line(ax, (xs[3] + 0.015 * L, -rs[3]), (xs[3] + 0.015 * L, rs[3]),
             f"Ø{res.De:.3f}", offset=(-0.03 * L, 0.45 * rs[3]), ha="right")

    # Angles
    xm = (xs[2] + xs[3]) / 2
    rm = (rs[2] + rs[3]) / 2 + wall
    ax.annotate(f"α = {inp.half_angle:.1f}°", (xm, rm),
                (xm + 0.02 * L, rm + 0.55 * R), fontsize=8.5, ha="center",
                arrowprops=dict(arrowstyle="-", color=WHITE, lw=0.6))
    xc = (xs[1] + xs[2]) / 2
    rc = (rs[1] + rs[2]) / 2 + wall
    ax.annotate(f"β = {inp.conv_angle:.1f}°", (xc, rc),
                (xc - 0.10 * L, rc + 0.30 * R), fontsize=8.5, ha="center",
                arrowprops=dict(arrowstyle="-", color=WHITE, lw=0.6))

    # Lengths
    y1 = -R * 1.35
    y2 = -R * 1.85
    for x in (0.0, *xs[1:]):
        ax.plot([x, x], [-R * 1.05, y2 - 0.08 * R], color=SOFT, lw=0.5)
    dim_line(ax, (0, y1), (xs[1], y1), f"{res.L_cylinder:.3f}")
    dim_line(ax, (xs[1], y1), (xs[2], y1), f"{res.L_converge:.3f}")
    dim_line(ax, (xs[2], y1), (xs[3], y1), f"{res.L_nozzle:.3f}")
    dim_line(ax, (0, y2), (xs[3], y2), f"OVERALL {res.L_total:.3f}")

    ax.set_xlim(-0.08 * L, 1.07 * L)
    ax.set_ylim(y2 - 0.35 * R, R * 1.75)

    # Station table (bottom left)
    tb = fig.add_axes([0.035, 0.04, 0.56, 0.27])
    tb.set_xlim(0, 1); tb.set_ylim(0, 1); tb.axis("off")
    tb.add_patch(Rectangle((0, 0), 1, 1, fill=False, ec=WHITE, lw=1.0))
    cols = ["STA", "LOCATION", "X in", "Ø in", "AREA in²", "P psia",
            "T °R", "MACH"]
    cx = [0.03, 0.10, 0.29, 0.40, 0.51, 0.65, 0.78, 0.91]
    rows = [
        ["0", "INJECTOR", "0.000", f"{res.Dc:.3f}", f"{res.Ac:.3f}",
         f"{inp.Pc:.1f}", f"{res.Tc:,.0f}", "≈0"],
        ["1", "CHAMBER", f"{xs[1]:.3f}", f"{res.Dc:.3f}", f"{res.Ac:.3f}",
         f"{inp.Pc:.1f}", f"{res.Tc:,.0f}", "≈0"],
        ["2", "THROAT", f"{xs[2]:.3f}", f"{res.Dt:.3f}", f"{res.At:.3f}",
         f"{res.P_throat:.1f}", f"{res.T_throat:,.0f}", "1.00"],
        ["3", "EXIT", f"{xs[3]:.3f}", f"{res.De:.3f}", f"{res.Ae:.3f}",
         f"{res.Pe:.2f}", f"{res.T_exit:,.0f}", f"{res.M_exit:.2f}"],
    ]
    tb.text(0.5, 0.91, "STATION DATA (EQUILIBRIUM)", ha="center",
            va="center", fontsize=9, fontweight="bold")
    tb.plot([0, 1], [0.82, 0.82], color=WHITE, lw=0.8)
    for x, c in zip(cx, cols):
        tb.text(x, 0.74, c, fontsize=8, color=SOFT, va="center")
    tb.plot([0, 1], [0.66, 0.66], color=WHITE, lw=0.5)
    for i, row in enumerate(rows):
        y = 0.57 - i * 0.125
        for x, v in zip(cx, row):
            tb.text(x, y, v, fontsize=8.5, va="center")
    tb.text(0.03, 0.04, f"γ = {res.gamma:.3f}   MW = {res.mol_wt:.2f}   "
            f"Cf,vac = {res.Cf_vac:.3f}   Cf,SL = {res.Cf_sl:.3f}   "
            f"L* = {inp.Lstar:.0f} in", fontsize=8, color=SOFT)

    # Title block (bottom right)
    tt = fig.add_axes([0.61, 0.04, 0.355, 0.27])
    tt.set_xlim(0, 1); tt.set_ylim(0, 1); tt.axis("off")
    tt.add_patch(Rectangle((0, 0), 1, 1, fill=False, ec=WHITE, lw=1.4))
    for y in (0.78, 0.60, 0.42, 0.24):
        tt.plot([0, 1], [y, y], color=WHITE, lw=0.6)
    tt.plot([0.5, 0.5], [0, 0.60], color=WHITE, lw=0.6)
    tt.text(0.5, 0.89, DRAWING_TITLE, ha="center", va="center",
            fontsize=10.5, fontweight="bold")

    def cell(x, y, label, value, size=9.5):
        tt.text(x + 0.02, y + 0.13, label, fontsize=6.5, color=SOFT,
                va="center")
        tt.text(x + 0.02, y + 0.05, value, fontsize=size, va="center",
                fontweight="bold")

    tt.text(0.02, 0.73, "PROPELLANTS / DESIGN POINT", fontsize=6.5,
            color=SOFT, va="center")
    tt.text(0.02, 0.655,
            f"{inp.ox} / {inp.fuel}   F = {inp.thrust:,.0f} lbf "
            f"({'SL' if inp.thrust_at_sea_level else 'VAC'})   "
            f"Pc = {inp.Pc:.0f} psia   O/F = {inp.MR:.2f}   ε = {inp.eps:.1f}",
            fontsize=8, va="center")
    cell(0.0, 0.42, "PROGRAM BY", AUTHOR.upper())
    cell(0.5, 0.42, "DATE", TODAY)
    cell(0.0, 0.24, "UNITS", "INCHES")
    cell(0.5, 0.24, "SCALE", "PROPORTIONAL")
    cell(0.0, 0.03, "DWG NO.", DWG_NO, size=8.5)
    cell(0.5, 0.03, "SHEET / REV", "1 OF 1 / A")
    return fig


def blueprint_axes(fig, ax):
    ax.grid(color=FAINT, lw=0.6)
    ax.tick_params(labelsize=8)
    fig.text(0.985, 0.015, AUTHOR.upper(), ha="right", va="bottom",
             fontsize=6.5, color=(1, 1, 1, 0.45))


tab_draw, tab_results, tab_trades, tab_method = st.tabs(
    ["DRAWING", "ANALYSIS", "TRADE STUDIES", "METHOD"])

with tab_draw:
    fig = draw_blueprint(res, inp)
    st.pyplot(fig)
    st.caption("Thrust chamber cross-section, drawn to proportion from the "
               "calculated geometry. Inside-wall dimensions; wall thickness "
               "is illustrative only.")
    png = io.BytesIO()
    fig.savefig(png, format="png", dpi=220)
    plt.close(fig)

    contour_df = pd.DataFrame(contour(res), columns=["x_in", "radius_in"])
    d1, d2, _ = st.columns([1, 1, 3])
    d1.download_button("Download drawing (PNG)", png.getvalue(),
                       f"{DWG_NO}.png", "image/png")
    d2.download_button("Download contour (CSV)",
                       contour_df.to_csv(index=False), f"{DWG_NO}_contour.csv",
                       "text/csv",
                       help="Corner points of the inside wall, for CAD.")


# ---------------------------------------------------------------------------
# Analysis tab: full results, station data, exhaust composition
# ---------------------------------------------------------------------------
IN, LB, PSI = 25.4, 0.45359237, 6.894757
rows = [
    ("Combustion", "Ideal vacuum Isp (CEA, axial exhaust)", res.Isp_vac_ideal, "s", res.Isp_vac_ideal, "s"),
    ("Combustion", "Vacuum specific impulse", res.Isp_vac, "s", res.Isp_vac, "s"),
    ("Combustion", "Sea-level specific impulse", res.Isp_sl, "s", res.Isp_sl, "s"),
    ("Combustion", "Characteristic velocity c*", res.cstar, "ft/s", res.cstar * 0.3048, "m/s"),
    ("Combustion", "Chamber temperature", res.Tc, "°R", res.Tc / 1.8, "K"),
    ("Combustion", "Ratio of specific heats γ", res.gamma, "-", res.gamma, "-"),
    ("Combustion", "Molecular weight", res.mol_wt, "lb/lbmol", res.mol_wt, "g/mol"),
    ("Nozzle", "Thrust coefficient Cf (vacuum)", res.Cf_vac, "-", res.Cf_vac, "-"),
    ("Nozzle", "Thrust coefficient Cf (sea level)", res.Cf_sl, "-", res.Cf_sl, "-"),
    ("Nozzle", "Divergence factor λ", res.div_factor, "-", res.div_factor, "-"),
    ("Nozzle", "Effective exhaust velocity (vacuum)", res.Isp_vac * engine.G0, "ft/s", res.Isp_vac * 9.80665, "m/s"),
    ("Nozzle", "Throat sonic velocity", res.v_throat, "ft/s", res.v_throat * 0.3048, "m/s"),
    ("Nozzle", "Exit Mach number", res.M_exit, "-", res.M_exit, "-"),
    ("Nozzle", "Exit pressure", res.Pe, "psia", res.Pe * PSI, "kPa"),
    ("Nozzle", "Sea-level optimum ε", res.eps_optimum, "-", res.eps_optimum, "-"),
    ("Thrust", "Thrust in vacuum", res.thrust_vac, "lbf", res.thrust_vac * 4.448222, "N"),
    ("Thrust", "Thrust at sea level", res.thrust_sl, "lbf", res.thrust_sl * 4.448222, "N"),
    ("Flow", "Total propellant flow", res.mdot, "lb/s", res.mdot * LB, "kg/s"),
    ("Flow", "Oxidizer flow", res.mdot_ox, "lb/s", res.mdot_ox * LB, "kg/s"),
    ("Flow", "Fuel flow", res.mdot_fuel, "lb/s", res.mdot_fuel * LB, "kg/s"),
    ("Geometry", "Throat area", res.At, "in²", res.At * IN**2, "mm²"),
    ("Geometry", "Throat diameter", res.Dt, "in", res.Dt * IN, "mm"),
    ("Geometry", "Exit area", res.Ae, "in²", res.Ae * IN**2, "mm²"),
    ("Geometry", "Exit diameter", res.De, "in", res.De * IN, "mm"),
    ("Geometry", "Chamber diameter", res.Dc, "in", res.Dc * IN, "mm"),
    ("Geometry", "Chamber volume", inp.Lstar * res.At, "in³", inp.Lstar * res.At * IN**3 / 1000, "cm³"),
    ("Geometry", "Chamber straight length", res.L_cylinder, "in", res.L_cylinder * IN, "mm"),
    ("Geometry", "Converging length", res.L_converge, "in", res.L_converge * IN, "mm"),
    ("Geometry", "Nozzle length", res.L_nozzle, "in", res.L_nozzle * IN, "mm"),
    ("Geometry", "Overall length", res.L_total, "in", res.L_total * IN, "mm"),
]
results_df = pd.DataFrame(
    rows, columns=["Group", "Quantity", "Value", "Unit", "SI value", "SI unit"])

with tab_results:
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Performance and geometry")
        shown = results_df.copy()
        for col in ("Value", "SI value"):
            shown[col] = shown[col].map(lambda v: f"{v:,.4g}")
        st.dataframe(shown, hide_index=True, width="stretch",
                     height=36 * (len(shown) + 1))
        st.download_button("Download results (CSV)",
                           results_df.to_csv(index=False),
                           f"{DWG_NO}_results.csv", "text/csv")
    with right:
        st.subheader("Exhaust composition")
        comp = cached_composition(settings)
        names = list(comp)[:8][::-1]
        y = np.arange(len(names))
        fig, ax = plt.subplots(figsize=(5.4, 4.2))
        ax.barh(y + 0.19, [comp[n][0] * 100 for n in names], 0.36,
                color=WHITE, label="Chamber")
        ax.barh(y - 0.19, [comp[n][1] * 100 for n in names], 0.36,
                color=CYAN, label="Nozzle exit")
        ax.set_yticks(y, names)
        ax.set_xlabel("Mole fraction (%)")
        ax.legend(frameon=False, fontsize=8, labelcolor=WHITE)
        blueprint_axes(fig, ax)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        st.caption("At chamber temperature some products break apart "
                   "(dissociation into CO, OH, H, O). As the gas cools in "
                   "the nozzle they partly recombine into CO₂ and H₂O.")
        st.caption("Apart from the conical nozzle's divergence loss, the "
                   "results assume an ideal engine. Real engines typically "
                   "reach 90-97% of the ideal CEA Isp.")


# ---------------------------------------------------------------------------
# Trade studies
# ---------------------------------------------------------------------------
def line_plot(x, ys, labels, xlabel, ylabel, current_x, colors=None):
    fig, ax = plt.subplots(figsize=(5.4, 3.5))
    colors = colors or [WHITE, CYAN]
    styles = ["-", (0, (5, 2))]
    for y, label, color, ls in zip(ys, labels, colors, styles):
        ax.plot(x, y, color=color, linewidth=1.8, label=label, linestyle=ls)
    ax.axvline(current_x, color=SOFT, linewidth=0.9, linestyle=(0, (2, 2)))
    ax.text(current_x, ax.get_ylim()[1], " DESIGN", color=SOFT, fontsize=7.5,
            va="top")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if len(ys) > 1:
        ax.legend(frameon=False, fontsize=8, labelcolor=WHITE)
    blueprint_axes(fig, ax)
    fig.tight_layout()
    return fig


with tab_trades:
    st.markdown("Each plot changes **one** input and holds the rest at the "
                "current design point.")

    mr0 = engine.DEFAULT_MR[(ox, fuel)]
    mr_vals = tuple(np.round(np.linspace(max(0.5, mr0 * 0.4),
                                         min(12.0, mr0 * 1.8), 40), 3))
    pc_vals = tuple(range(100, 1501, 50))
    eps_vals = tuple(np.round(np.linspace(2, 40, 39), 2))

    mr_s = cached_sweep(settings, "MR", mr_vals)
    pc_s = cached_sweep(settings, "Pc", pc_vals)
    eps_s = cached_sweep(settings, "eps", eps_vals)

    a, b = st.columns(2)
    with a:
        st.markdown("**Isp vs mixture ratio**")
        x = [v for v, _ in mr_s]
        isp = [r.Isp_vac for _, r in mr_s]
        st.pyplot(line_plot(x, [isp], ["Isp vac"], "O/F", "Isp vac (s)", MR))
        best = x[int(np.argmax(isp))]
        st.caption(f"Isp peaks near O/F = {best:.1f} ({max(isp):.1f} s). "
                   f"Design: {MR:.1f} ({res.Isp_vac:.1f} s).")
    with b:
        st.markdown("**Chamber temperature vs mixture ratio**")
        st.pyplot(line_plot(x, [[r.Tc for _, r in mr_s]], ["Tc"], "O/F",
                            "Tc (°R)", MR, colors=[CYAN]))
        st.caption("Hotter gas is harder on the chamber walls, so peak Isp "
                   "is not automatically the best design.")

    a, b = st.columns(2)
    with a:
        st.markdown("**Isp vs chamber pressure**")
        x = [v for v, _ in pc_s]
        st.pyplot(line_plot(x, [[r.Isp_vac for _, r in pc_s],
                                [r.Isp_sl for _, r in pc_s]],
                            ["Vacuum", "Sea level"], "Pc (psia)", "Isp (s)",
                            Pc))
        st.caption("Vacuum Isp barely changes. Sea-level Isp improves because "
                   "higher pressure overcomes the outside air.")
    with b:
        st.markdown("**Throat diameter vs chamber pressure**")
        st.pyplot(line_plot(x, [[r.Dt for _, r in pc_s]], ["Dt"],
                            "Pc (psia)", "Throat Ø (in)", Pc, colors=[CYAN]))
        st.caption("Higher pressure shrinks the engine, at the cost of "
                   "heavier tanks and thicker walls.")

    a, b = st.columns(2)
    with a:
        st.markdown("**Isp vs expansion ratio**")
        x = [v for v, _ in eps_s]
        st.pyplot(line_plot(x, [[r.Isp_vac for _, r in eps_s],
                                [r.Isp_sl for _, r in eps_s]],
                            ["Vacuum", "Sea level"], "ε = Ae/At", "Isp (s)",
                            eps))
        st.caption("In vacuum a bigger nozzle always helps. At sea level the "
                   f"optimum is ε ≈ {res.eps_optimum:.1f} at this Pc.")
    with b:
        st.markdown("**Nozzle length vs expansion ratio**")
        st.pyplot(line_plot(x, [[r.L_nozzle for _, r in eps_s]], ["Ln"],
                            "ε = Ae/At", "Nozzle length (in)", eps,
                            colors=[CYAN]))
        st.caption("The extra Isp is paid for in nozzle length and weight.")
    plt.close("all")


# ---------------------------------------------------------------------------
# Method
# ---------------------------------------------------------------------------
with tab_method:
    Isp_d = res.Isp_sl if inp.thrust_at_sea_level else res.Isp_vac
    st.markdown("""
The tool sizes the thrust chamber in four stages. Values shown are the
current design point.

**1. Thermochemistry (NASA CEA).** For the chosen propellants, mixture ratio
and chamber pressure, NASA's Chemical Equilibrium with Applications program
solves for the equilibrium combustion products and returns Isp, c\\*,
temperatures, γ and molecular weight at each station.

CEA assumes the exhaust leaves perfectly straight back. In a conical nozzle
it leaves spread over the half-angle α, so only a fraction λ of the exit
momentum produces thrust. The Isp used from here on has that loss removed
(v_e is the gas speed at the exit; the pressure thrust is unaffected).
""")
    st.latex(rf"\lambda = \frac{{1+\cos\alpha}}{{2}} = {res.div_factor:.4f}\qquad "
             rf"I_{{sp}} = I_{{sp,CEA}} - (1-\lambda)\frac{{v_e}}{{g_0}}"
             rf" = {res.Isp_vac_ideal:.1f} - {res.Isp_vac_ideal - res.Isp_vac:.1f}"
             rf" = {res.Isp_vac:.1f}\ \mathrm{{s\ (vac)}}")
    st.markdown("""
**2. Mass flow.** Specific impulse is thrust per unit propellant flow, so the
flow rate is thrust divided by Isp. The mixture ratio splits it into fuel and
oxidizer.
""")
    st.latex(rf"\dot m = \frac{{F}}{{I_{{sp}}}} = \frac{{{thrust:,.0f}}}{{{Isp_d:.1f}}}"
             rf" = {res.mdot:.3f}\ \mathrm{{lb/s}}\qquad"
             rf"\dot m_f = \frac{{\dot m}}{{1+O/F}} = {res.mdot_fuel:.3f}\qquad"
             rf"\dot m_o = {res.mdot_ox:.3f}")
    st.markdown("**3. Throat, exit and chamber areas.** c\\* relates mass "
                "flow, chamber pressure and throat area. The expansion and "
                "contraction ratios scale that area to the exit and chamber.")
    st.latex(rf"A_t = \frac{{\dot m\,c^*}}{{P_c\,g_0}} = {res.At:.4f}\ \mathrm{{in^2}}"
             rf"\qquad A_e = \varepsilon A_t\qquad A_c = \frac{{A_c}}{{A_t}}A_t"
             rf"\qquad D = 2\sqrt{{A/\pi}}")
    st.markdown("**4. Lengths.** Converging and diverging walls are straight "
                "cones, so each length comes from a right triangle. Chamber "
                "volume comes from the characteristic length L\\*.")
    st.latex(rf"L_n = \frac{{R_e - R_t}}{{\tan\alpha}} = {res.L_nozzle:.3f}\ \mathrm{{in}}"
             rf"\qquad V_c = L^* A_t = {inp.Lstar * res.At:.2f}\ \mathrm{{in^3}}"
             rf"\qquad L_{{cyl}} = \frac{{V_c - V_{{conv}}}}{{A_c}} = {res.L_cylinder:.3f}\ \mathrm{{in}}")
    st.markdown("**Thrust coefficient.** Thrust can also be written as "
                "F = Cf · Pc · At. Cf scores the nozzle on its own, the way c\\* "
                "scores the combustion. Because At was sized from c\\*, this "
                "is a consistency identity, not an independent check.")
    st.latex(rf"C_F = \frac{{F}}{{P_c A_t}} = {res.Cf_vac:.3f}\ (\mathrm{{vac}}),"
             rf"\quad {res.Cf_sl:.3f}\ (\mathrm{{SL}})"
             rf"\qquad I_{{sp}} = \frac{{c^* C_F}}{{g_0}}")
    st.markdown(f"""
**Assumptions and limits**

- Equilibrium chemistry with no friction, heat loss or incomplete
  combustion. The only loss included is the conical nozzle's divergence loss.
- Conical nozzle with sharp corners. Real nozzles round the throat and often
  use a bell contour, which has a smaller divergence loss.
- No cooling, wall thickness, injector or structural design.
- Preliminary sizing only, not a build-ready design.

---
Rocket Engine Sizing Tool · program by **{AUTHOR}**
""")
