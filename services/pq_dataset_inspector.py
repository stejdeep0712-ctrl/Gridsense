
import csv
import math
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parents[1]

DATASET_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "pq_simulation_dataset.csv"
)

def inspect_dataset():

    if not DATASET_FILE.exists():
        print("ERROR: PQ dataset not found.")
        return

    with open(DATASET_FILE, "r", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        print("ERROR: Dataset is empty.")
        return

    print("\n========== PQ DATASET REPORT ==========")

    print(f"Total scenarios: {len(rows)}")
    print(f"Total columns: {len(rows[0])}")

    print("\n--- CLASS DISTRIBUTION ---")

    labels = Counter(
        row["pq_limit_exceeded"] for row in rows
    )

    print(f"Class 0 (Within VUF limit): {labels.get('0', 0)}")
    print(f"Class 1 (VUF limit exceeded): {labels.get('1', 0)}")

    print("\n--- MISSING VALUES ---")

    missing_count = 0

    for column in rows[0].keys():
        missing = sum(
            1 for row in rows
            if row[column] is None or row[column].strip() == ""
        )

        if missing > 0:
            print(f"{column}: {missing} missing values")
            missing_count += missing

    if missing_count == 0:
        print("No missing values found.")

    print("\n--- VUF STATISTICS ---")

    vuf_values = [
        float(row["voltage_unbalance_percent"])
        for row in rows
    ]

    print(f"Minimum VUF: {min(vuf_values):.4f}%")
    print(f"Maximum VUF: {max(vuf_values):.4f}%")
    print(f"Average VUF: {sum(vuf_values) / len(vuf_values):.4f}%")

    print("\n--- VOLTAGE STATISTICS ---")

    voltage_values = []

    for row in rows:
        for column in [
            "phase_a_voltage_pu",
            "phase_b_voltage_pu",
            "phase_c_voltage_pu"
        ]:
            voltage_values.append(float(row[column]))

    print(f"Minimum phase voltage: {min(voltage_values):.4f} pu")
    print(f"Maximum phase voltage: {max(voltage_values):.4f} pu")

    print("\n--- DUPLICATE CHECK ---")

    unique_rows = {
        tuple(row.values()) for row in rows
    }

    duplicates = len(rows) - len(unique_rows)

    print(f"Duplicate records: {duplicates}")

    print("\n--- POWER FLOW CHECK ---")

    converged = sum(
        1 for row in rows
        if row["power_flow_converged"].strip().lower() in ("true", "1", "yes")
    )

    print(f"Converged scenarios: {converged}")
    print(f"Failed scenarios: {len(rows) - converged}")

    print("\n--- DATA QUALITY CHECK ---")

    if len(labels) < 2:
        print("WARNING: Only one class exists. Do not train yet.")
    elif missing_count > 0:
        print("WARNING: Missing values need investigation.")
    elif converged != len(rows):
        print("WARNING: Some power flows did not converge.")
    elif not all(math.isfinite(value) for value in vuf_values):
        print("WARNING: Invalid VUF values detected.")
    else:
        print("Basic checks passed. Dataset is ready for further review.")

    print("\n=======================================")


if __name__ == "__main__":
    inspect_dataset()

