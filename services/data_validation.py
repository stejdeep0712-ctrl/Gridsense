
from services.csv_loader import load_feeder_data

REQUIRED_FIELDS = [
    "feeder_id",
    "peak_load",
    "min_load",
    "transformer_rating",
    "existing_solar",
    "voltage",
    "nominal_voltage",
    "voltage_unbalance",
    "thd",
    "power_factor",
    "line_resistance",
    "line_reactance",
    "hosting_capacity",
    "pq_incident"
]

NUMERIC_FIELDS = REQUIRED_FIELDS[1:]


def validate_feeder_data(data):

    errors = []
    feeder_ids = set()

    for row_number, row in enumerate(data, start=1):

        feeder_id = row.get("feeder_id", "").strip()

        # Check missing fields
        for field in REQUIRED_FIELDS:
            if not row.get(field, "").strip():
                errors.append(
                    f"Row {row_number}: Missing {field}"
                )

        # Check duplicate feeder IDs
        if feeder_id:
            if feeder_id in feeder_ids:
                errors.append(
                    f"Row {row_number}: Duplicate feeder ID {feeder_id}"
                )
            feeder_ids.add(feeder_id)

        # Check numerical values
        for field in NUMERIC_FIELDS:

            try:
                value = float(row[field])

                if value < 0:
                    errors.append(
                        f"Row {row_number}: Negative value in {field}"
                    )

            except (ValueError, KeyError):
                errors.append(
                    f"Row {row_number}: Invalid number in {field}"
                )

        # Check power factor
        try:
            pf = float(row["power_factor"])
            if not 0 <= pf <= 1:
                errors.append(
                    f"Row {row_number}: Invalid power factor"
                )
        except (ValueError, KeyError):
            pass

        # Check classification label
        try:
            label = int(row["pq_incident"])
            if label not in (0, 1):
                errors.append(
                    f"Row {row_number}: pq_incident must be 0 or 1"
                )
        except (ValueError, KeyError):
            pass

    return errors


if __name__ == "__main__":

    feeder_data = load_feeder_data()

    errors = validate_feeder_data(feeder_data)

    print("TOTAL RECORDS:", len(feeder_data))

    if errors:
        print("\nDATA VALIDATION FAILED")

        for error in errors:
            print(error)

    else:
        print("\nDATA VALIDATION PASSED!")
        print("No basic data-quality errors found.")
