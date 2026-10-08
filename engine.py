"""
engine.py - the engineering math for the rocket engine sizing tool.

This file has NO user interface in it. It only does calculations, in the same
order we worked them out by hand:

    Stage 1  combustion numbers from NASA CEA   (Isp, c*, chamber temperature)
    Stage 2  propellant flow rates              (total, fuel, oxidizer)
    Stage 3  areas and diameters                (throat, exit, chamber)
    Stage 4  lengths and the nozzle outline     (for the drawing)

app.py imports this file and puts buttons and plots on top of it.

Units are imperial throughout: lbf, lb/s, psia, inches, ft/s, degrees Rankine.
"""

import math
from dataclasses import dataclass

from rocketcea.cea_obj import CEA_Obj

G0 = 32.174            # standard gravity, ft/s^2 (converts lb-mass to lb-force)
SEA_LEVEL_PSIA = 14.7  # air pressure at sea level

# Display name -> the name NASA CEA uses for it
OXIDIZERS = {
    "Liquid oxygen (LOX)": "LOX",
    "Nitrous oxide (N2O)": "N2O",
}
FUELS = {
    "Methane (CH4)": "CH4",
    "Kerosene (RP-1)": "RP1",
    "Hydrogen (LH2)": "LH2",
    "Ethanol": "Ethanol",
    "Propane": "Propane",
}

# A sensible starting mixture ratio for each pair (near its best Isp).
DEFAULT_MR = {
    ("LOX", "CH4"): 3.3,
    ("LOX", "RP1"): 2.4,
    ("LOX", "LH2"): 4.0,
    ("LOX", "Ethanol"): 1.7,
    ("LOX", "Propane"): 2.6,
    ("N2O", "CH4"): 9.7,
    ("N2O", "RP1"): 8.0,
    ("N2O", "LH2"): 9.3,
    ("N2O", "Ethanol"): 5.3,
    ("N2O", "Propane"): 8.6,
}


@dataclass
class Inputs:
    """Everything the designer chooses."""
    ox: str = "LOX"                 # oxidizer (CEA name)
    fuel: str = "CH4"               # fuel (CEA name)
    thrust: float = 500.0           # target thrust, lbf
    Pc: float = 300.0               # chamber pressure, psia
    MR: float = 3.3                 # mixture ratio = oxidizer mass / fuel mass
    eps: float = 8.0                # expansion ratio = exit area / throat area
    thrust_at_sea_level: bool = False   # False: thrust is met in vacuum
    contraction_ratio: float = 6.0  # chamber area / throat area
    Lstar: float = 40.0             # characteristic chamber length, inches
    half_angle: float = 15.0        # diverging nozzle wall angle, degrees
    conv_angle: float = 30.0        # converging wall angle, degrees


@dataclass
class Results:
    """Everything the tool calculates."""
    # Stage 1: combustion
    Isp_vac: float      # s, after the conical nozzle's divergence loss
    Isp_sl: float       # s, after the conical nozzle's divergence loss
    Isp_vac_ideal: float  # s, straight from CEA (perfectly axial exhaust)
    div_factor: float   # lambda = (1 + cos(alpha)) / 2, share of exit momentum pointing straight back
    sl_condition: str   # what CEA says the flow is doing at sea level
    cstar: float        # ft/s
    Tc: float           # degrees Rankine
    Pe: float           # exit pressure, psia
    eps_optimum: float  # expansion ratio where exit pressure = sea level
    # Stage 2: flow rates, lb/s
    mdot: float
    mdot_fuel: float
    mdot_ox: float
    # Thrust this engine makes in each condition, lbf
    thrust_vac: float
    thrust_sl: float
    # Stage 3: areas (in^2) and diameters (in)
    At: float
    Dt: float
    Ae: float
    De: float
    Ac: float
    Dc: float
    # Stage 4: lengths, inches
    L_nozzle: float     # throat to exit
    L_converge: float   # end of cylinder to throat
    L_cylinder: float   # straight part of the chamber
    L_total: float      # injector face to nozzle exit
    # Gas properties at the three stations: chamber, throat, exit
    T_throat: float     # degrees Rankine
    T_exit: float
    P_throat: float     # psia
    M_exit: float       # exit Mach number (throat is always Mach 1)
    gamma: float        # ratio of specific heats in the chamber
    mol_wt: float       # molecular weight of chamber gas, lb/lb-mol
    v_throat: float     # speed of sound at the throat, ft/s
    # Thrust coefficient: how much the nozzle multiplies Pc * At
    Cf_vac: float
    Cf_sl: float


def circle_diameter(area):
    """Diameter of a circle from its area:  d = 2 * sqrt(A / pi)."""
    return 2 * math.sqrt(area / math.pi)


def cone_volume(r_big, r_small, length):
    """Volume of a cone with its tip cut off (a frustum)."""
    return math.pi * length / 3 * (r_big**2 + r_big * r_small + r_small**2)


def size_engine(inp: Inputs) -> Results:
    """Run the whole sizing calculation for one set of design choices."""

    # ---- Stage 1: ask NASA CEA how the propellants burn --------------------
    cea = CEA_Obj(oxName=inp.ox, fuelName=inp.fuel)

    Isp_vac_ideal = cea.get_Isp(Pc=inp.Pc, MR=inp.MR, eps=inp.eps)
    cstar = cea.get_Cstar(Pc=inp.Pc, MR=inp.MR)
    Tc = cea.get_Tcomb(Pc=inp.Pc, MR=inp.MR)

    # Sea-level performance: outside air pushes back on the exhaust.
    Isp_sl_ideal, sl_condition = cea.estimate_Ambient_Isp(
        Pc=inp.Pc, MR=inp.MR, eps=inp.eps, Pamb=SEA_LEVEL_PSIA)

    # CEA assumes all the exhaust leaves straight back. In a cone it leaves
    # spread over the half-angle, so only a fraction lambda of the exit
    # momentum pushes the engine forward (Sutton, Rocket Propulsion Elements).
    # The pressure part of the thrust is unaffected.
    div_factor = (1 + math.cos(math.radians(inp.half_angle))) / 2
    M_exit = cea.get_MachNumber(Pc=inp.Pc, MR=inp.MR, eps=inp.eps)
    v_exit = M_exit * cea.get_SonicVelocities(
        Pc=inp.Pc, MR=inp.MR, eps=inp.eps)[2]          # gas speed at exit, ft/s
    Isp_loss = (1 - div_factor) * v_exit / G0
    Isp_vac = Isp_vac_ideal - Isp_loss
    Isp_sl = Isp_sl_ideal - Isp_loss

    # Pressure of the exhaust as it leaves the nozzle.
    Pe = inp.Pc / cea.get_PcOvPe(Pc=inp.Pc, MR=inp.MR, eps=inp.eps)

    # The expansion ratio that would make exit pressure equal sea-level air.
    eps_optimum = cea.get_eps_at_PcOvPe(
        Pc=inp.Pc, MR=inp.MR, PcOvPe=inp.Pc / SEA_LEVEL_PSIA)

    # ---- Stage 2: flow rates -----------------------------------------------
    # Isp = thrust / flow rate   ->   flow rate = thrust / Isp
    Isp_design = Isp_sl if inp.thrust_at_sea_level else Isp_vac
    mdot = inp.thrust / Isp_design

    # One "batch" is 1 lb of fuel + MR lb of oxidizer.
    mdot_fuel = mdot / (1 + inp.MR)
    mdot_ox = mdot - mdot_fuel

    # ---- Stage 3: areas and diameters --------------------------------------
    # Throat: more flow -> bigger, more pressure -> smaller.
    At = mdot * cstar / (inp.Pc * G0)
    Ae = At * inp.eps                  # expansion ratio = Ae / At
    Ac = At * inp.contraction_ratio    # contraction ratio = Ac / At

    Dt = circle_diameter(At)
    De = circle_diameter(Ae)
    Dc = circle_diameter(Ac)
    Rt, Re, Rc = Dt / 2, De / 2, Dc / 2

    # ---- Stage 4: lengths --------------------------------------------------
    # Right triangle: tan(angle) = (radius change) / length
    L_nozzle = (Re - Rt) / math.tan(math.radians(inp.half_angle))
    L_converge = (Rc - Rt) / math.tan(math.radians(inp.conv_angle))

    # L* = chamber volume / throat area. It sets how long the gas stays in
    # the chamber, so the propellants have time to finish burning.
    V_chamber = inp.Lstar * At
    V_converge = cone_volume(Rc, Rt, L_converge)
    L_cylinder = max((V_chamber - V_converge) / Ac, 0.0)

    # ---- Station properties ------------------------------------------------
    _, T_throat, T_exit = cea.get_Temperatures(Pc=inp.Pc, MR=inp.MR, eps=inp.eps)
    P_throat = inp.Pc / cea.get_Throat_PcOvPe(Pc=inp.Pc, MR=inp.MR)
    mol_wt, gamma = cea.get_Chamber_MolWt_gamma(Pc=inp.Pc, MR=inp.MR, eps=inp.eps)
    v_throat = cea.get_SonicVelocities(Pc=inp.Pc, MR=inp.MR, eps=inp.eps)[1]

    # Thrust = Cf * Pc * At, so Cf = thrust / (Pc * At)
    thrust_vac = mdot * float(Isp_vac)
    thrust_sl = mdot * float(Isp_sl)
    Cf_vac = thrust_vac / (inp.Pc * At)
    Cf_sl = thrust_sl / (inp.Pc * At)

    return Results(
        Isp_vac=float(Isp_vac), Isp_sl=float(Isp_sl),
        Isp_vac_ideal=float(Isp_vac_ideal), div_factor=div_factor,
        sl_condition=sl_condition,
        cstar=float(cstar), Tc=float(Tc), Pe=float(Pe),
        eps_optimum=float(eps_optimum),
        mdot=mdot, mdot_fuel=mdot_fuel, mdot_ox=mdot_ox,
        thrust_vac=thrust_vac, thrust_sl=thrust_sl,
        At=At, Dt=Dt, Ae=Ae, De=De, Ac=Ac, Dc=Dc,
        L_nozzle=L_nozzle, L_converge=L_converge, L_cylinder=L_cylinder,
        L_total=L_cylinder + L_converge + L_nozzle,
        T_throat=float(T_throat), T_exit=float(T_exit),
        P_throat=float(P_throat), M_exit=float(M_exit),
        gamma=float(gamma), mol_wt=float(mol_wt), v_throat=float(v_throat),
        Cf_vac=Cf_vac, Cf_sl=Cf_sl,
    )


def composition(inp: Inputs, min_fraction=0.005):
    """
    What the hot gas is made of, as mole fractions, in the chamber and at
    the nozzle exit. Returns {species: (chamber, exit)}, largest first.
    A '*' in CEA's names just marks a gas species; we strip it.
    """
    cea = CEA_Obj(oxName=inp.ox, fuelName=inp.fuel)
    _, fractions = cea.get_SpeciesMoleFractions(
        Pc=inp.Pc, MR=inp.MR, eps=inp.eps, min_fraction=min_fraction)
    out = {name.lstrip("*"): (float(v[1]), float(v[3]))
           for name, v in fractions.items()}
    return dict(sorted(out.items(), key=lambda kv: -kv[1][0]))


def contour(res: Results):
    """
    Corner points of the inside wall, as (x, radius) pairs in inches.
    x = 0 is the injector face, where the propellants enter.
    """
    x1 = res.L_cylinder
    x2 = x1 + res.L_converge
    x3 = x2 + res.L_nozzle
    return [
        (0.0, res.Dc / 2),   # injector face
        (x1, res.Dc / 2),    # end of the straight chamber
        (x2, res.Dt / 2),    # throat
        (x3, res.De / 2),    # nozzle exit
    ]


def sweep(inp: Inputs, name: str, values):
    """
    Re-run the sizing while changing ONE input (name is "Pc", "MR" or "eps")
    and keeping everything else fixed. This is a trade study.
    Returns a list of (value, Results).
    """
    out = []
    for v in values:
        trial = Inputs(**{**inp.__dict__, name: float(v)})
        try:
            out.append((float(v), size_engine(trial)))
        except Exception:
            pass   # skip any point where CEA cannot find a solution
    return out


def air_pressure(altitude_ft):
    """
    U.S. Standard Atmosphere (1976) air pressure in psia, valid to 167,000 ft.
    Each layer has either a steady temperature drop (lapse) or a constant
    temperature, which sets how fast pressure falls with height.
    """
    h = altitude_ft * 0.3048                          # metres
    if h < 11000:      # troposphere: temperature falls 6.5 K per km
        return 14.696 * (1 - 2.25577e-5 * h) ** 5.25588
    if h < 20000:      # lower stratosphere: constant 216.65 K
        return 3.2825 * math.exp(-(h - 11000) / 6341.62)
    if h < 32000:      # temperature rises 1 K per km
        return 0.79406 * (1 + (h - 20000) / 216650) ** -34.1632
    if h < 47000:      # temperature rises 2.8 K per km
        return 0.125897 * (1 + 2.8 * (h - 32000) / 228650) ** -12.2011
    # constant 270.65 K (47-51 km)
    return 0.016085 * math.exp(-(h - 47000) / 7922.3)


def altitude_performance(inp: Inputs, res: Results, altitudes_ft):
    """
    Thrust and Isp of THIS engine (fixed size, fixed flow rate) as it climbs.
    Returns a list of (altitude, air pressure, Isp, thrust, flow condition).
    """
    cea = CEA_Obj(oxName=inp.ox, fuelName=inp.fuel)
    loss = res.Isp_vac_ideal - res.Isp_vac     # conical divergence loss, s
    out = []
    for h in altitudes_ft:
        Pamb = air_pressure(h)
        Isp, condition = cea.estimate_Ambient_Isp(
            Pc=inp.Pc, MR=inp.MR, eps=inp.eps, Pamb=Pamb)
        Isp = float(Isp) - loss
        out.append((float(h), Pamb, float(Isp), res.mdot * float(Isp),
                    condition.split(" ")[0]))
    return out


# Running "python engine.py" prints the baseline design as a quick check.
if __name__ == "__main__":
    r = size_engine(Inputs())
    for key, value in r.__dict__.items():
        print(f"{key:14s} {value}")
    print(composition(Inputs()))
    for row in altitude_performance(Inputs(), r, [0, 10000, 30000, 60000, 100000]):
        print(row)
