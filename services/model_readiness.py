
import csv
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_FILE = BASE_DIR / "data" / "processed" / "ml_dataset.csv"


def check_model_readiness():

    if not DATA_FILE.exists():
        print("Processed dataset not found!")
        return

    with open(DATA_FILE, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        data = list(reader)

    if not data:
        print("Dataset is empty!")
        return

    print("=" * 45)
    print("       MACHINE LEARNING DATASET AUDIT")
    print("=" * 45)

    # Total records
    print("\n1. Total feeder records:", len(data))

    # Unique feeder IDs
    feeder_ids = [row["feeder_id"] for row in data]
    print("2. Unique feeder IDs:", len(set(feeder_ids)))

    if len(feeder_ids) != len(set(feeder_ids)):
        print("WARNING: Duplicate feeder IDs found!")

    # Classification target distribution
    labels = Counter(row["pq_incident"] for row in data)

    print("\n3. Classification target distribution:")
    for label, count in sorted(labels.items()):
        print(f"   Class {label}: {count} records")

    # Regression target range
    capacities = [
        float(row["hosting_capacity"])
        for row in data
    ]

    print("\n4. Regression target:")
    print("   Minimum:", min(capacities))
    print("   Maximum:", max(capacities))

    # Check required columns
    print("\n5. Missing values:")

    missing = 0

    for row_number, row in enumerate(data, start=1):
        for column, value in row.items():
            if value is None or value.strip() == "":
                print(f"   Row {row_number}: Missing {column}")
                missing += 1

    if missing == 0:
        print("   No missing values found.")

    # Final assessment
    print("\n6. MODEL READINESS")

    if len(data) < 100:
        print("   INSUFFICIENT DATA FOR CREDIBLE MODEL TRAINING")

    if len(labels) < 2:
        print("   Classification needs both classes.")

    if len(set(feeder_ids)) < 2:
        print("   More independent feeders are required.")

    print("\nNOTE:")
    print("Current records are synthetic demonstration data.")
    print("Do not report model accuracy using this dataset.")

    print("\nAUDIT COMPLETED!")


if __name__ == "__main__":
    check_model_readiness()
