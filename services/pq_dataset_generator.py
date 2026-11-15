
import csv
from itertools import product
from pathlib import Path

import opendssdirect as dss
import services.pq_simulation as pq


# =========================================
# PATHS AND SETTINGS
# =========================================

BASE_DIR = Path(__file__).resolve().parents[1]

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "pq_multifeeder_dataset.csv"
)

VUF_SCREENING_LIMIT_PERCENT = 2.0


# =========================================
# FOUR FEEDER CONFIGURATIONS
# =========================================

FEEDER_CONFIGURATIONS = [

    {
        "feeder_id": "FDR_SHORT",
        "length_km": 0.2,
        "r1": 0.05,
        "x1": 0.04
    },

    {
        "feeder_id": "FDR_MEDIUM",
        "length_km": 0.5,
        "r1": 0.08,
        "x1": 0.06
    },

    {
        "feeder_id": "FDR_LONG",
        "length_km": 1.0,
        "r1": 0.12,
        "x1": 0.09
    },

    {
        "feeder_id": "FDR_HIGH_IMPEDANCE",
        "length_km": 2.0,
        "r1": 0.20,
        "x1": 0.15
    }

]


# =========================================
# PHASE LOAD SCENARIOS
# =========================================

PHASE_A_LEVELS = [20, 30, 40, 50, 60, 70, 80]
PHASE_B_LEVELS = [5, 10, 15, 20]
PHASE_C_LEVELS = [5, 10, 15, 20]


# =========================================
# GENERATE DATASET
# =========================================

def generate_dataset():

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    phase_scenarios = list(product(
        PHASE_A_LEVELS,
        PHASE_B_LEVELS,
        PHASE_C_LEVELS
    ))

    scenarios = list(product(
        FEEDER_CONFIGURATIONS,
        phase_scenarios
    ))

    successful = 0
    failed = 0

    class_counts = {0: 0, 1: 0}
    feeder_counts = {}

    columns = [
        "scenario_id",
        "feeder_id",
        "line_length_km",
        "line_r1",
        "line_x1",
        "phase_a_load_kw",
        "phase_b_load_kw",
        "phase_c_load_kw",
        "phase_a_voltage_pu",
        "phase_b_voltage_pu",
        "phase_c_voltage_pu",
        "minimum_voltage_pu",
        "maximum_voltage_pu",
        "positive_sequence_voltage_pu",
        "negative_sequence_voltage_pu",
        "voltage_unbalance_percent",
        "vuf_screening_limit_percent",
        "pq_limit_exceeded",
        "power_flow_converged"
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=columns
        )

        writer.writeheader()

        for index, scenario in enumerate(
            scenarios,
            start=1
        ):

            feeder, phase_loads = scenario

            length = feeder["length_km"]
            r1 = feeder["r1"]
            x1 = feeder["x1"]

            phase_a, phase_b, phase_c = phase_loads

            feeder_id = feeder["feeder_id"]

            try:

                # Load a clean feeder for every scenario
                pq.load_feeder()

                # Apply line parameters
                pq.configure_feeder_line(
                    length,
                    r1,
                    x1
                )

                # Set phase loads
                pq.PHASE_A_LOAD_KW = phase_a
                pq.PHASE_B_LOAD_KW = phase_b
                pq.PHASE_C_LOAD_KW = phase_c

                pq.add_phase_loads()

                # Solve power flow
                dss.Solution.Solve()

                if not dss.Solution.Converged():

                    failed += 1

                    feeder_counts.setdefault(
                        feeder_id,
                        {"successful": 0, "failed": 0}
                    )

                    feeder_counts[feeder_id]["failed"] += 1

                    print(
                        f"Scenario {index} did not converge."
                    )

                    continue

                # Read voltages at EndBus
                phase_voltages = pq.get_phase_voltages(
                    "EndBus"
                )

                vuf, positive, negative = (
                    pq.calculate_vuf(phase_voltages)
                )

                voltage_magnitudes = {
                    phase: abs(value)
                    for phase, value in phase_voltages.items()
                }

                min_voltage = min(
                    voltage_magnitudes.values()
                )

                max_voltage = max(
                    voltage_magnitudes.values()
                )

                # Create VUF threshold label
                label = int(
                    vuf > VUF_SCREENING_LIMIT_PERCENT
                )

                writer.writerow({

                    "scenario_id": f"PQ{index:04d}",

                    "feeder_id": feeder_id,

                    "line_length_km": length,
                    "line_r1": r1,
                    "line_x1": x1,

                    "phase_a_load_kw": phase_a,
                    "phase_b_load_kw": phase_b,
                    "phase_c_load_kw": phase_c,

                    "phase_a_voltage_pu": voltage_magnitudes[1],
                    "phase_b_voltage_pu": voltage_magnitudes[2],
                    "phase_c_voltage_pu": voltage_magnitudes[3],

                    "minimum_voltage_pu": min_voltage,
                    "maximum_voltage_pu": max_voltage,

                    "positive_sequence_voltage_pu": positive,
                    "negative_sequence_voltage_pu": negative,

                    "voltage_unbalance_percent": vuf,

                    "vuf_screening_limit_percent":
                        VUF_SCREENING_LIMIT_PERCENT,

                    "pq_limit_exceeded": label,

                    "power_flow_converged": 1

                })

                successful += 1
                class_counts[label] += 1

                feeder_counts.setdefault(
                    feeder_id,
                    {"successful": 0, "failed": 0}
                )

                feeder_counts[feeder_id]["successful"] += 1

            except Exception as error:

                failed += 1

                feeder_counts.setdefault(
                    feeder_id,
                    {"successful": 0, "failed": 0}
                )

                feeder_counts[feeder_id]["failed"] += 1

                print(
                    f"Scenario {index} ({feeder_id}) failed: {error}"
                )

    # =====================================
    # PRINT DATASET SUMMARY
    # =====================================

    print("\n========== MULTI-CONFIGURATION PQ DATASET ==========")

    print(f"Total attempted scenarios: {len(scenarios)}")
    print(f"Successful scenarios: {successful}")
    print(f"Failed scenarios: {failed}")

    print(f"Class 0: {class_counts[0]}")
    print(f"Class 1: {class_counts[1]}")

    print("\nFEEDER SUMMARY")

    for feeder_id, counts in feeder_counts.items():

        print(
            f"{feeder_id}: "
            f"{counts['successful']} successful, "
            f"{counts['failed']} failed"
        )

    print(f"\nDataset saved at: {OUTPUT_FILE}")

    print("\nIMPORTANT:")
    print(
        "These are parameterized configurations of one "
        "demonstration network topology."
    )

    print(
        "Labels represent simulated VUF threshold exceedance, "
        "not historical PQ incidents."
    )

    print(
        "The 2% threshold is an illustrative project "
        "screening threshold, not a universal regulatory limit."
    )

    print("======================================================")


if __name__ == "__main__":
    generate_dataset()
