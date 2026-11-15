
import csv
import math
from pathlib import Path

import opendssdirect as dss


# -----------------------------------------
# PROJECT PATHS
# -----------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

DSS_FILE = BASE_DIR / "data" / "opendss" / "master.dss"

OUTPUT_DIR = BASE_DIR / "data" / "processed"

OUTPUT_FILE = OUTPUT_DIR / "hosting_capacity_sweep.csv"


# -----------------------------------------
# SIMULATION SETTINGS
# -----------------------------------------

START_SOLAR_KW = 0
MAX_SOLAR_KW = 500
STEP_KW = 25

MIN_VOLTAGE_PU = 0.95
MAX_VOLTAGE_PU = 1.05

# Keep inverter rating fixed during this
# preliminary solar generation sweep.
INVERTER_RATING_KVA = 600


# -----------------------------------------
# GET BUS VOLTAGE MEASUREMENTS
# -----------------------------------------

def get_bus_voltage_values():

    bus_names = dss.Circuit.AllBusNames()

    voltage_values = []

    for bus in bus_names:

        dss.Circuit.SetActiveBus(bus)

        voltage_data = dss.Bus.puVmagAngle()

        # Values are stored as:
        # magnitude, angle, magnitude, angle...

        for i in range(0, len(voltage_data), 2):

            voltage = voltage_data[i]

            if voltage > 0 and math.isfinite(voltage):
                voltage_values.append(voltage)

    if not voltage_values:
        raise RuntimeError(
            "No valid bus voltage measurements found."
        )

    return min(voltage_values), max(voltage_values)


# -----------------------------------------
# RUN HOSTING CAPACITY SWEEP
# -----------------------------------------

def run_hosting_capacity_sweep():

    if not DSS_FILE.exists():
        raise FileNotFoundError(
            f"OpenDSS file not found: {DSS_FILE}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load feeder circuit
    dss.Text.Command("Clear")
    dss.Text.Command(f'Compile "{DSS_FILE}"')

    results = []

    first_violation_kw = None
    last_contiguous_pass_kw = None
    violation_found = False

    print("=" * 55)
    print("       SOLAR HOSTING CAPACITY SIMULATION")
    print("=" * 55)

    print("\nSolar generation sweep:")
    print(f"Start: {START_SOLAR_KW} kW")
    print(f"Maximum: {MAX_SOLAR_KW} kW")
    print(f"Increment: {STEP_KW} kW")

    print("\nVoltage limits:")
    print(f"Minimum: {MIN_VOLTAGE_PU} pu")
    print(f"Maximum: {MAX_VOLTAGE_PU} pu")

    print("\nRUNNING SIMULATIONS...\n")

    # Increase solar generation gradually
    for solar_kw in range(
        START_SOLAR_KW,
        MAX_SOLAR_KW + 1,
        STEP_KW
    ):

        # Modify solar PV system
        dss.Text.Command(
            f"Edit PVSystem.RooftopPV "
            f"pmpp={solar_kw} "
            f"kVA={INVERTER_RATING_KVA} "
            f"irradiance=1"
        )

        # Solve power flow
        dss.Text.Command("Solve")

        converged = dss.Solution.Converged()

        if not converged:

            print(
                f"{solar_kw} kW | "
                "Power flow did not converge"
            )

            results.append({
                "solar_generation_kw": solar_kw,
                "minimum_voltage_pu": "",
                "maximum_voltage_pu": "",
                "power_flow_converged": False,
                "voltage_status": "NOT_EVALUATED"
            })

            if first_violation_kw is None:
                first_violation_kw = solar_kw

            violation_found = True
            continue

        # Measure bus voltages
        min_voltage, max_voltage = get_bus_voltage_values()

        # Check voltage limits
        voltage_ok = (
            MIN_VOLTAGE_PU <= min_voltage
            and max_voltage <= MAX_VOLTAGE_PU
        )

        if voltage_ok:

            status = "PASS"

            if not violation_found:
                last_contiguous_pass_kw = solar_kw

        else:

            status = "VOLTAGE_VIOLATION"

            if first_violation_kw is None:
                first_violation_kw = solar_kw

            violation_found = True

        print(
            f"Solar: {solar_kw:>3} kW | "
            f"Min V: {min_voltage:.4f} pu | "
            f"Max V: {max_voltage:.4f} pu | "
            f"{status}"
        )

        results.append({
            "solar_generation_kw": solar_kw,
            "minimum_voltage_pu": round(min_voltage, 5),
            "maximum_voltage_pu": round(max_voltage, 5),
            "power_flow_converged": True,
            "voltage_status": status
        })

    # -------------------------------------
    # SAVE RESULTS TO CSV
    # -------------------------------------

    fieldnames = [
        "solar_generation_kw",
        "minimum_voltage_pu",
        "maximum_voltage_pu",
        "power_flow_converged",
        "voltage_status"
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(results)

    # -------------------------------------
    # DISPLAY SUMMARY
    # -------------------------------------

    print("\n" + "=" * 55)
    print("              SIMULATION SUMMARY")
    print("=" * 55)

    if first_violation_kw is not None:

        print(
            "First tested violation:",
            first_violation_kw,
            "kW"
        )

        print(
            "Last contiguous passing test:",
            last_contiguous_pass_kw,
            "kW"
        )

        print(
            "\nPreliminary voltage-limited estimate:",
            last_contiguous_pass_kw,
            "kW"
        )

    else:

        print(
            f"No voltage violation found up to "
            f"{MAX_SOLAR_KW} kW."
        )

        print(
            "Hosting capacity is at least "
            f"{MAX_SOLAR_KW} kW under these "
            "voltage checks; the upper limit "
            "has not been established."
        )

    print("\nResults saved to:")
    print(OUTPUT_FILE)

    print("\nSIMULATION COMPLETED!")


# -----------------------------------------
# MAIN PROGRAM
# -----------------------------------------

if __name__ == "__main__":
    run_hosting_capacity_sweep()
