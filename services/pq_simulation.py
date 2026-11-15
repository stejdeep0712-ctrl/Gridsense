
import math
from pathlib import Path

import opendssdirect as dss


# =========================================
# PROJECT CONFIGURATION
# =========================================

BASE_DIR = Path(__file__).resolve().parents[1]

DSS_FILE = BASE_DIR / "data" / "opendss" / "master.dss"

PHASE_A_LOAD_KW = 20
PHASE_B_LOAD_KW = 10
PHASE_C_LOAD_KW = 5

PHASE_VOLTAGE_KV = 0.277

TARGET_BUSES = ["LoadBus", "EndBus"]


# =========================================
# LOAD OPENDSS FEEDER
# =========================================

def load_feeder():

    if not DSS_FILE.exists():
        raise FileNotFoundError(
            f"OpenDSS file not found: {DSS_FILE}"
        )

    dss.Text.Command("Clear")
    dss.Text.Command(f'Compile "{DSS_FILE}"')


# =========================================
# CONFIGURE FEEDER LINE
# =========================================

def configure_feeder_line(length_km, r1, x1):

    command = (
        f"Edit Line.FeederLine "
        f"length={length_km} "
        f"r1={r1} "
        f"x1={x1}"
    )

    dss.Text.Command(command)


# =========================================
# ADD UNBALANCED PHASE LOADS
# =========================================

def add_phase_loads():

    commands = [

        (
            f"New Load.PQPhaseA phases=1 "
            f"bus1=EndBus.1 conn=wye "
            f"kV={PHASE_VOLTAGE_KV} "
            f"kW={PHASE_A_LOAD_KW} pf=0.95"
        ),

        (
            f"New Load.PQPhaseB phases=1 "
            f"bus1=EndBus.2 conn=wye "
            f"kV={PHASE_VOLTAGE_KV} "
            f"kW={PHASE_B_LOAD_KW} pf=0.95"
        ),

        (
            f"New Load.PQPhaseC phases=1 "
            f"bus1=EndBus.3 conn=wye "
            f"kV={PHASE_VOLTAGE_KV} "
            f"kW={PHASE_C_LOAD_KW} pf=0.95"
        )

    ]

    for command in commands:
        dss.Text.Command(command)


# =========================================
# GET THREE-PHASE VOLTAGES
# =========================================

def get_phase_voltages(bus_name):

    dss.Circuit.SetActiveBus(bus_name)

    nodes = dss.Bus.Nodes()
    voltage_data = dss.Bus.puVmagAngle()

    phase_voltages = {}

    for index, node in enumerate(nodes):

        if node not in (1, 2, 3):
            continue

        magnitude = voltage_data[index * 2]
        angle_degrees = voltage_data[index * 2 + 1]

        if not math.isfinite(magnitude):
            continue

        angle_radians = math.radians(angle_degrees)

        phase_voltages[node] = (
            magnitude * complex(
                math.cos(angle_radians),
                math.sin(angle_radians)
            )
        )

    if not all(
        phase in phase_voltages
        for phase in (1, 2, 3)
    ):
        raise RuntimeError(
            f"Bus {bus_name} does not have all three phases. "
            f"Found nodes: {nodes}"
        )

    return phase_voltages


# =========================================
# CALCULATE VOLTAGE UNBALANCE FACTOR
# =========================================

def calculate_vuf(phase_voltages):

    va = phase_voltages[1]
    vb = phase_voltages[2]
    vc = phase_voltages[3]

    a = complex(
        math.cos(2 * math.pi / 3),
        math.sin(2 * math.pi / 3)
    )

    a_squared = a * a

    v1 = (
        va + a * vb + a_squared * vc
    ) / 3

    v2 = (
        va + a_squared * vb + a * vc
    ) / 3

    if abs(v1) < 1e-12:
        raise RuntimeError(
            "Positive sequence voltage is too small."
        )

    vuf = (abs(v2) / abs(v1)) * 100

    return vuf, abs(v1), abs(v2)


# =========================================
# RUN SINGLE PQ SIMULATION
# =========================================

def run_pq_simulation():

    print("=" * 60)
    print("       OPENDSS POWER QUALITY SIMULATION")
    print("=" * 60)

    load_feeder()
    add_phase_loads()

    dss.Solution.Solve()

    if not dss.Solution.Converged():
        raise RuntimeError(
            "OpenDSS power flow did not converge."
        )

    print("\nPOWER FLOW STATUS")
    print("Converged:", dss.Solution.Converged())

    print("\nPHASE LOAD CONFIGURATION")
    print("Phase A:", PHASE_A_LOAD_KW, "kW")
    print("Phase B:", PHASE_B_LOAD_KW, "kW")
    print("Phase C:", PHASE_C_LOAD_KW, "kW")

    print("\nVOLTAGE UNBALANCE RESULTS")
    print("-" * 60)

    for bus_name in TARGET_BUSES:

        phase_voltages = get_phase_voltages(bus_name)

        vuf, positive, negative = calculate_vuf(
            phase_voltages
        )

        print(f"\nBus: {bus_name}")

        for phase in (1, 2, 3):

            voltage = abs(phase_voltages[phase])

            print(
                f"Phase {phase}: {voltage:.5f} pu"
            )

        print(f"Positive sequence: {positive:.6f} pu")
        print(f"Negative sequence: {negative:.6f} pu")
        print(f"Voltage Unbalance Factor: {vuf:.5f}%")

    print("\n" + "=" * 60)
    print("POWER QUALITY SIMULATION COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    run_pq_simulation()
