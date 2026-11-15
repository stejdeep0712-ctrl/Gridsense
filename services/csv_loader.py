
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = BASE_DIR / "data" / "raw" / "feeder_data.csv"


def load_feeder_data(file_path=DATA_FILE):

    records = []

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:

        reader = csv.reader(file)

        # Remove blank and whitespace-only rows
        rows = [
            [value.strip() for value in row]
            for row in reader
            if any(value.strip() for value in row)
        ]

        if not rows:
            raise ValueError("CSV file is empty!")

        # First non-empty row is the header
        headers = rows[0]

        # Remaining rows are feeder records
        for row in rows[1:]:
            if len(row) != len(headers):
                print("Skipping invalid row:", row)
                continue

            record = dict(zip(headers, row))
            records.append(record)

    return records


if __name__ == "__main__":

    data = load_feeder_data()

    print("Dataset loaded successfully!")
    print("Total feeder records:", len(data))

    print("\nFirst feeder:")
    print(data[0] if data else "No feeder records found")
