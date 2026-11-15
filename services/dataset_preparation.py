
import csv
from pathlib import Path

from services.csv_loader import load_feeder_data
from services.data_validation import validate_feeder_data
from services.feature_engineering import engineer_features


BASE_DIR = Path(__file__).resolve().parents[1]

OUTPUT_DIR = BASE_DIR / "data" / "processed"

OUTPUT_FILE = OUTPUT_DIR / "ml_dataset.csv"


# Only these columns are allowed as model inputs.
# Target columns are deliberately excluded.
FEATURE_COLUMNS = [
    "peak_load",
    "min_load",
    "transformer_rating",
    "existing_solar",
    "transformer_loading",
    "solar_penetration",
    "voltage_deviation",
    "load_range",
    "line_impedance",
    "voltage_unbalance",
    "thd",
    "power_factor"
]

TARGET_COLUMNS = [
    "hosting_capacity",
    "pq_incident"
]


def prepare_dataset():

    # Load original data
    raw_data = load_feeder_data()

    # Validate original data
    errors = validate_feeder_data(raw_data)

    if errors:
        print("DATA VALIDATION FAILED")

        for error in errors:
            print(error)

        return

    # Engineer additional features
    data = engineer_features(raw_data)

    # Create processed folder
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Define output columns
    columns = (
        ["feeder_id"]
        + FEATURE_COLUMNS
        + TARGET_COLUMNS
    )

    # Save processed dataset
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

        for row in data:

            processed_row = {
                "feeder_id": row["feeder_id"]
            }

            for column in FEATURE_COLUMNS:
                processed_row[column] = row[column]

            for column in TARGET_COLUMNS:
                processed_row[column] = row[column]

            writer.writerow(processed_row)

    print("ML DATASET PREPARED SUCCESSFULLY!")

    print("Total records:", len(data))
    print("Input features:", len(FEATURE_COLUMNS))
    print("Regression target: hosting_capacity")
    print("Classification target: pq_incident")

    print("\nSaved file:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    prepare_dataset()
