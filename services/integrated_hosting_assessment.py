
from pathlib import Path
import csv
import math
import opendssdirect as dss


# =========================================
# PROJECT PATHS
# =========================================

BASE_DIR = Path(__file__).resolve().parents[1]

DSS_FILE = BASE_DIR / "data" / "opendss" / "master.dss"

OUTPUT_DIR = BASE_DIR / "data" / "processed"

OUTPUT_FILE = OUTPUT_DIR / "integrated_hosting_results.csv"


# =========================================
# ENGINEERING LIMITS
# =========================================

MIN_VOLTAGE_PU = 0.95
MAX_VOLTAGE_PU = 1.05

TRANSFORMER_RATING_KVA = 1000

LINE_NORMAL_LIMIT_AMPS = 400

SOLAR_LEVELS = range(0, 501, 25)

INVERTER_RATING_KVA = 600


# =========================================
# VOLTAGE MEASUREMENTS
# =========================================

def get_voltage_measurements():

    bus_names = dss.Circuit.AllBusNames()

    values = []

    for bus in bus_names:

        dss.Circuit.SetActiveBus(bus)

        voltage_data = dss.Bus.puVmagAngle()

        for i in range(0, len(voltage_data), 2):

            voltage = voltage_data[i]

            if voltage > 0 and math.isfinite(voltage):
                values.append(voltage)

    if not values:
        raise RuntimeError("No valid voltage measurements!")

    return min(values), max(values)


# =========================================
# TRANSFORMER MEASUREMENTS
# =========================================

def get_transformer_loading():

    success = dss.Circuit.SetActiveElement(
        "Transformer.SubXf"
    )

    if not success:
        raise RuntimeError("Transformer not found!")

    powers = dss.CktElement.Powers()

    # First terminal, three phases
    active_power = sum(powers[i] for i in [0, 2, 4])
    reactive_power = sum(powers[i] for i in [1, 3, 5])

    apparent_power = math.hypot(
        active_power,
        reactive_power
    )

    loading_percent = (
        apparent_power / TRANSFORMER_RATING_KVA
    ) * 100

    return apparent_power, loading_percent


# =========================================
# LINE MEASUREMENTS
# =========================================

def get_line_loading():

    success = dss.Circuit.SetActiveElement(
        "Line.FeederLine"
    )

    if not success:
        raise RuntimeError("Distribution line not found!")

    current_data = dss.CktElement.CurrentsMagAng()

    phase_currents = [
        current_data[0],
        current_data[2],
        current_data[4]
    ]

    maximum_current = max(phase_currents)

    loading_percent = (
        maximum_current / LINE_NORMAL_LIMIT_AMPS
    ) * 100

    return maximum_current, loading_percent


# =========================================
# MAIN ASSESSMENT
# =========================================

def run_integrated_assessment():

    if not DSS_FILE.exists():
        raise FileNotFoundError(DSS_FILE)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dss.Text.Command("Clear")
    dss.Text.Command(f'Compile "{DSS_FILE}"')

    results = []

    first_violation = None
    last_contiguous_pass = None
    violation_seen = False

    print("=" * 75)
    print("        INTEGRATED SOLAR HOSTING CAPACITY ASSESSMENT")
    print("=" * 75)

    print(
        "\nSolar | Min V | Max V | Transformer % | Line % | Result"
    )

    for solar_kw in SOLAR_LEVELS:

        # Update solar generation
        dss.Text.Command(
            f"Edit PVSystem.RooftopPV "
            f"pmpp={solar_kw} "
            f"kVA={INVERTER_RATING_KVA} "
            f"irradiance=1"
        )

        # Solve power flow
        dss.Text.Command("Solve")

        if not dss.Solution.Converged():

            results.append({
                "solar_kw": solar_kw,
                "minimum_voltage_pu": "",
                "maximum_voltage_pu": "",
                "transformer_kva": "",
                "transformer_loading_percent": "",
                "maximum_line_current_amps": "",
                "line_loading_percent": "",
                "result": "NON_CONVERGED"
            })

            if first_violation is None:
                first_violation = solar_kw

            violation_seen = True

            print(
                f"{solar_kw:>3} kW | "
                "POWER FLOW DID NOT CONVERGE"
            )

            continue

        # Measure voltage
        min_voltage, max_voltage = get_voltage_measurements()

        # Measure transformer
        transformer_kva, transformer_percent = (
            get_transformer_loading()
        )

        # Measure line
        line_current, line_percent = get_line_loading()

        # Check individual constraints
        voltage_ok = (
            min_voltage >= MIN_VOLTAGE_PU
            and max_voltage <= MAX_VOLTAGE_PU
        )

        transformer_ok = (
            transformer_percent <= 100
        )

        line_ok = (
            line_current <= LINE_NORMAL_LIMIT_AMPS
        )

        # Identify limiting factors
        limiting_factors = []

        if not voltage_ok:
            limiting_factors.append("VOLTAGE")

        if not transformer_ok:
            limiting_factors.append("TRANSFORMER")

        if not line_ok:
            limiting_factors.append("LINE")

        if limiting_factors:
            status = "FAIL: " + ",".join(limiting_factors)

            if first_violation is None:
                first_violation = solar_kw

            violation_seen = True

        else:
            status = "PASS"

            if not violation_seen:
                last_contiguous_pass = solar_kw

        print(
            f"{solar_kw:>3} kW | "
            f"{min_voltage:.4f} | "
            f"{max_voltage:.4f} | "
            f"{transformer_percent:>8.2f}% | "
            f"{line_percent:>6.2f}% | "
            f"{status}"
        )

        results.append({
            "solar_kw": solar_kw,
            "minimum_voltage_pu": round(min_voltage, 5),
            "maximum_voltage_pu": round(max_voltage, 5),
            "transformer_kva": round(transformer_kva, 3),
            "transformer_loading_percent": round(
                transformer_percent, 3
            ),
            "maximum_line_current_amps": round(
                line_current, 3
            ),
            "line_loading_percent": round(
                line_percent, 3
            ),
            "result": status
        })

    # =====================================
    # SAVE RESULTS
    # =====================================

    fieldnames = [
        "solar_kw",
        "minimum_voltage_pu",
        "maximum_voltage_pu",
        "transformer_kva",
        "transformer_loading_percent",
        "maximum_line_current_amps",
        "line_loading_percent",
        "result"
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

    # =====================================
    # FINAL SUMMARY
    # =====================================

    print("\n" + "=" * 75)
    print("                 ASSESSMENT SUMMARY")
    print("=" * 75)

    if first_violation is not None:

        print("First tested violation:", first_violation, "kW")

        print(
            "Last contiguous passing test:",
            last_contiguous_pass,
            "kW"
        )

        if last_contiguous_pass is not None:

            print(
                "Preliminary tested limit:",
                last_contiguous_pass,
                "kW"
            )

        else:
            print(
                "No passing solar level found in the tested range."
            )

    else:

        print("No violations found in the tested range.")

        print(
            f"Capacity is at least {max(SOLAR_LEVELS)} kW "
            "under the three tested constraints."
        )

    print("\nResults saved to:")
    print(OUTPUT_FILE)

    print("\nASSESSMENT COMPLETED!")


if __name__ == "__main__":
    run_integrated_assessment()
