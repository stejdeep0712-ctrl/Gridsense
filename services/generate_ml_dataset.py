
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

OUTPUT_FILE = OUTPUT_DIR / "ml_training_dataset.csv"


# =========================================
# SIMULATION CONFIGURATION
# =========================================

TRANSFORMER_RATING_KVA = 1000

LINE_RATING_AMPS = 400

# Increased inverter rating for expanded solar sweep.
INVERTER_RATING_KVA = 1200

MIN_VOLTAGE_PU = 0.95

MAX_VOLTAGE_PU = 1.05

# Expanded maximum additional solar capacity.
MAX_NEW_SOLAR_KW = 800

SOLAR_STEP_KW = 25


# =========================================
# FEEDER CONFIGURATIONS
# =========================================

LOAD_LEVELS = [180, 220, 260, 300, 340]

LINE_LENGTHS = [0.1, 0.2, 0.3, 0.4, 0.5]

EXISTING_SOLAR_LEVELS = [50, 100, 150, 200]


# =========================================
# CREATE FEEDER PROFILES
# =========================================

def create_feeder_profiles():

    profiles = []

    feeder_number = 1

    for load in LOAD_LEVELS:

        for length in LINE_LENGTHS:

            for existing_solar in EXISTING_SOLAR_LEVELS:

                profiles.append({

                    "feeder_id": f"SIM{feeder_number:03d}",

                    "peak_load_kw": load,

                    "line_length_km": length,

                    "existing_solar_kw": existing_solar

                })

                feeder_number += 1

    return profiles


# =========================================
# MEASURE BUS VOLTAGES
# =========================================

def get_voltage_measurements():

    values = []

    for bus in dss.Circuit.AllBusNames():

        dss.Circuit.SetActiveBus(bus)

        voltage_data = dss.Bus.puVmagAngle()

        for i in range(0, len(voltage_data), 2):

            voltage = voltage_data[i]

            if voltage > 0 and math.isfinite(voltage):

                values.append(voltage)

    if not values:

        raise RuntimeError(
            "No valid voltage measurements"
        )

    return min(values), max(values)


# =========================================
# MEASURE TRANSFORMER LOADING
# =========================================

def get_transformer_measurements():

    success = dss.Circuit.SetActiveElement(
        "Transformer.SubXf"
    )

    if not success:

        raise RuntimeError(
            "Transformer not found"
        )

    powers = dss.CktElement.Powers()

    active_power = sum(
        powers[i] for i in [0, 2, 4]
    )

    reactive_power = sum(
        powers[i] for i in [1, 3, 5]
    )

    apparent_power = math.hypot(
        active_power,
        reactive_power
    )

    loading_percent = (
        apparent_power / TRANSFORMER_RATING_KVA
    ) * 100

    return apparent_power, loading_percent


# =========================================
# MEASURE LINE CURRENT
# =========================================

def get_line_measurements():

    success = dss.Circuit.SetActiveElement(
        "Line.FeederLine"
    )

    if not success:

        raise RuntimeError(
            "Feeder line not found"
        )

    current_data = dss.CktElement.CurrentsMagAng()

    phase_currents = [

        current_data[0],

        current_data[2],

        current_data[4]

    ]

    maximum_current = max(phase_currents)

    loading_percent = (
        maximum_current / LINE_RATING_AMPS
    ) * 100

    return maximum_current, loading_percent


# =========================================
# SIMULATE ONE FEEDER
# =========================================

def simulate_feeder(profile):

    dss.Text.Command("Clear")

    dss.Text.Command(
        f'Compile "{DSS_FILE}"'
    )

    # -------------------------------------
    # CHANGE FEEDER LOAD
    # -------------------------------------

    dss.Text.Command(
        f"Edit Load.FeederLoad "
        f"kw={profile['peak_load_kw']}"
    )

    # -------------------------------------
    # CHANGE LINE LENGTH
    # -------------------------------------

    dss.Text.Command(
        f"Edit Line.FeederLine "
        f"length={profile['line_length_km']}"
    )

    feeder_records = []

    last_passing_capacity = None

    violation_seen = False

    # -------------------------------------
    # TEST NEW SOLAR CONNECTION SIZES
    # -------------------------------------

    for requested_solar in range(
        0,
        MAX_NEW_SOLAR_KW + 1,
        SOLAR_STEP_KW
    ):

        total_solar = (
            profile["existing_solar_kw"]
            + requested_solar
        )

        # ---------------------------------
        # UPDATE SOLAR PV SYSTEM
        # ---------------------------------

        dss.Text.Command(
            f"Edit PVSystem.RooftopPV "
            f"pmpp={total_solar} "
            f"kVA={INVERTER_RATING_KVA} "
            f"irradiance=1"
        )

        dss.Text.Command("Solve")

        # ---------------------------------
        # CHECK POWER FLOW CONVERGENCE
        # ---------------------------------

        if not dss.Solution.Converged():

            feeder_records.append({

                "feeder_id": profile["feeder_id"],

                "peak_load_kw": profile["peak_load_kw"],

                "line_length_km": profile["line_length_km"],

                "existing_solar_kw": profile["existing_solar_kw"],

                "requested_solar_kw": requested_solar,

                "total_solar_kw": total_solar,

                "minimum_voltage_pu": "",

                "maximum_voltage_pu": "",

                "transformer_loading_percent": "",

                "maximum_line_current_amps": "",

                "line_loading_percent": "",

                "power_flow_converged": 0,

                "constraint_violation": 1

            })

            violation_seen = True

            continue

        # ---------------------------------
        # COLLECT ELECTRICAL MEASUREMENTS
        # ---------------------------------

        min_voltage, max_voltage = (
            get_voltage_measurements()
        )

        transformer_kva, transformer_loading = (
            get_transformer_measurements()
        )

        line_current, line_loading = (
            get_line_measurements()
        )

        # ---------------------------------
        # CHECK ENGINEERING CONSTRAINTS
        # ---------------------------------

        voltage_ok = (

            min_voltage >= MIN_VOLTAGE_PU

            and max_voltage <= MAX_VOLTAGE_PU

        )

        transformer_ok = (
            transformer_loading <= 100
        )

        line_ok = (
            line_current <= LINE_RATING_AMPS
        )

        passed = (

            voltage_ok

            and transformer_ok

            and line_ok

        )

        constraint_violation = (
            0 if passed else 1
        )

        # ---------------------------------
        # FIND LAST CONTIGUOUS PASSING SIZE
        # ---------------------------------

        if passed and not violation_seen:

            last_passing_capacity = requested_solar

        else:

            violation_seen = True

        # ---------------------------------
        # SAVE SIMULATION RECORD
        # ---------------------------------

        feeder_records.append({

            "feeder_id": profile["feeder_id"],

            "peak_load_kw": profile["peak_load_kw"],

            "line_length_km": profile["line_length_km"],

            "existing_solar_kw": profile["existing_solar_kw"],

            "requested_solar_kw": requested_solar,

            "total_solar_kw": total_solar,

            "minimum_voltage_pu": round(
                min_voltage, 5
            ),

            "maximum_voltage_pu": round(
                max_voltage, 5
            ),

            "transformer_loading_percent": round(
                transformer_loading, 3
            ),

            "maximum_line_current_amps": round(
                line_current, 3
            ),

            "line_loading_percent": round(
                line_loading, 3
            ),

            "power_flow_converged": 1,

            "constraint_violation": constraint_violation

        })

    # -------------------------------------
    # ADD REGRESSION TARGET
    # -------------------------------------

    for record in feeder_records:

        record["hosting_capacity_kw"] = (
            last_passing_capacity
            if last_passing_capacity is not None
            else 0
        )

    # -------------------------------------
    # DETECT RIGHT-CENSORED CONFIGURATION
    # -------------------------------------

    reached_maximum = (
        last_passing_capacity == MAX_NEW_SOLAR_KW
    )

    return (
        feeder_records,
        last_passing_capacity,
        reached_maximum
    )


# =========================================
# GENERATE COMPLETE DATASET
# =========================================

def generate_dataset():

    if not DSS_FILE.exists():

        raise FileNotFoundError(DSS_FILE)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    profiles = create_feeder_profiles()

    all_records = []

    successful_configurations = 0

    baseline_failures = 0

    no_capacity_configurations = 0

    right_censored_configurations = 0

    print("=" * 65)

    print(
        "       GRIDSENSE OPEN DSS ML DATASET GENERATOR"
    )

    print("=" * 65)

    print(
        "\nTotal planned feeder configurations:",
        len(profiles)
    )

    print(
        "Load levels:",
        LOAD_LEVELS
    )

    print(
        "Line lengths:",
        LINE_LENGTHS
    )

    print(
        "Existing solar levels:",
        EXISTING_SOLAR_LEVELS
    )

    print(
        "Maximum additional solar:",
        MAX_NEW_SOLAR_KW,
        "kW"
    )

    print(
        "Solar step:",
        SOLAR_STEP_KW,
        "kW"
    )

    print(
        "Inverter rating:",
        INVERTER_RATING_KVA,
        "kVA"
    )

    # -------------------------------------
    # SIMULATE EVERY FEEDER
    # -------------------------------------

    for profile in profiles:

        print(
            f"\nSimulating {profile['feeder_id']} | "
            f"Load: {profile['peak_load_kw']} kW | "
            f"Line: {profile['line_length_km']} km | "
            f"Existing Solar: "
            f"{profile['existing_solar_kw']} kW"
        )

        records, capacity, reached_maximum = (
            simulate_feeder(profile)
        )

        # ---------------------------------
        # CHECK BASELINE
        # ---------------------------------

        baseline = records[0]

        if baseline["constraint_violation"] == 1:

            baseline_failures += 1

            print(
                "Skipped: baseline feeder violates "
                "a configured limit."
            )

            continue

        # ---------------------------------
        # CHECK CAPACITY BOUNDARY
        # ---------------------------------

        if capacity is None:

            no_capacity_configurations += 1

            print(
                "Skipped: no contiguous passing "
                "capacity found."
            )

            continue

        successful_configurations += 1

        # ---------------------------------
        # CHECK RIGHT-CENSORING
        # ---------------------------------

        if reached_maximum:

            right_censored_configurations += 1

            print(
                "Right-censored: simulation still passes "
                "at the maximum tested capacity of",
                MAX_NEW_SOLAR_KW,
                "kW."
            )

        else:

            print(
                "Demonstrated additional solar capacity:",
                capacity,
                "kW"
            )

        # Keep successful configurations in the
        # dataset. The regression trainer must
        # exclude right-censored targets.
        all_records.extend(records)

    # -------------------------------------
    # CHECK GENERATED DATASET
    # -------------------------------------

    if not all_records:

        raise RuntimeError(
            "No valid feeder records generated."
        )

    # -------------------------------------
    # SAVE DATASET
    # -------------------------------------

    fieldnames = list(all_records[0].keys())

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

        writer.writerows(all_records)

    # -------------------------------------
    # DATASET SUMMARY
    # -------------------------------------

    unique_feeders = len({

        row["feeder_id"]

        for row in all_records

    })

    class_zero = sum(

        1 for row in all_records

        if row["power_flow_converged"] == 1
        and row["constraint_violation"] == 0

    )

    class_one = sum(

        1 for row in all_records

        if row["power_flow_converged"] == 1
        and row["constraint_violation"] == 1

    )

    distinct_targets = sorted({

        row["hosting_capacity_kw"]

        for row in all_records

        if row["power_flow_converged"] == 1

    })

    print("\n" + "=" * 65)

    print("                 DATASET SUMMARY")

    print("=" * 65)

    print(
        "Planned configurations:",
        len(profiles)
    )

    print(
        "Successful configurations:",
        successful_configurations
    )

    print(
        "Baseline failures:",
        baseline_failures
    )

    print(
        "No capacity configurations:",
        no_capacity_configurations
    )

    print(
        "Right-censored configurations:",
        right_censored_configurations
    )

    print(
        "Configurations in dataset:",
        unique_feeders
    )

    print(
        "Total simulation records:",
        len(all_records)
    )

    print(
        "Class 0 records:",
        class_zero
    )

    print(
        "Class 1 records:",
        class_one
    )

    print(
        "Distinct hosting-capacity targets:",
        len(distinct_targets)
    )

    print(
        "Target values:",
        distinct_targets
    )

    print("\nRegression target: hosting_capacity_kw")

    print("Classification target: constraint_violation")

    print("\nSaved dataset:")

    print(OUTPUT_FILE)

    print("\nDATASET GENERATION COMPLETED!")


# =========================================
# MAIN
# =========================================

if __name__ == "__main__":

    generate_dataset()
