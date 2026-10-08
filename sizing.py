from rocketcea.cea_obj import CEA_Obj
import math

# Design choices
ox = 'LOX'      # liquid oxygen
fuel = 'CH4'    # liquid methane
Pc = 300        # chamber pressure, psia
MR = 3.3        # mixture ratio: mass of oxidizer / mass of fuel
eps = 8         # expansion ratio: exit area / throat area

engine = CEA_Obj(oxName=ox, fuelName=fuel)

Isp = engine.get_Isp(Pc=Pc, MR=MR, eps=eps)
cstar = engine.get_Cstar(Pc=Pc, MR=MR)
Tc = engine.get_Tcomb(Pc=Pc, MR=MR)

print("Isp (s):", Isp)
print("c* (ft/s):", cstar)
print("Chamber temp (R):", Tc)

F = 500         # target thrust, lbf
mdot = F / Isp
print("Total flow rate (lb/s):", mdot)

mdot_fuel = mdot / (1 + MR)
mdot_ox = mdot - mdot_fuel

print("Methane flow (lb/s):", mdot_fuel)
print("Oxygen flow (lb/s):", mdot_ox)

g0 = 32.174     # standard gravity, ft/s^2

At = mdot * cstar / (Pc * g0)
print("Throat area (in^2):", At)

Dt = 2 * math.sqrt(At / math.pi)
print("Throat diameter (in):", Dt)

Ae = At * eps
De = 2 * math.sqrt(Ae / math.pi)

print("Exit area (in^2):", Ae)
print("Exit diameter (in):", De)

half_angle = 15   # nozzle wall angle, degrees

Rt = Dt / 2
Re = De / 2
Ln = (Re - Rt) / math.tan(math.radians(half_angle))

print("Nozzle length (in):", Ln)