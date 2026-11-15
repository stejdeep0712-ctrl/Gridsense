
from services.csv_loader import load_feeder_data
from services.data_validation import validate_feeder_data


def engineer_features(data):

    engineered_data = []

    for row in data:

        # Convert raw values into numbers
        peak_load = float(row["peak_load"])
        min_load = float(row["min_load"])
        transformer_rating = float(row["transformer_rating"])
        existing_solar = float(row["existing_solar"])

        voltage = float(row["voltage"])
        nominal_voltage = float(row["nominal_voltage"])

        voltage_unbalance = float(row["voltage_unbalance"])
        thd = float(row["thd"])
        power_factor = float(row["power_factor"])

        line_resistance = float(row["line_resistance"])
        line_reactance = float(row["line_reactance"])

        # Avoid division by zero
        if transformer_rating <= 0 or nominal_voltage <= 0:
            raise ValueError(
                f"Invalid rating or nominal voltage for {row['feeder_id']}"
            )

        # Feature 1: Transformer loading ratio
        transformer_loading = peak_load / transformer_rating

        # Feature 2: Solar penetration ratio
        solar_penetration = existing_solar / transformer_rating

        # Feature 3: Voltage deviation percentage
        voltage_deviation = (
            (voltage - nominal_voltage) / nominal_voltage
        ) * 100

        # Feature 4: Load range
        load_range = peak_load - min_load

        # Feature 5: Line impedance magnitude
        line_impedance = (
            line_resistance ** 2 + line_reactance ** 2
        ) ** 0.5

        features = {
            "feeder_id": row["feeder_id"],

            "peak_load": peak_load,
            "min_load": min_load,
            "transformer_rating": transformer_rating,
            "existing_solar": existing_solar,

            "transformer_loading": transformer_loading,
            "solar_penetration": solar_penetration,
            "voltage_deviation": voltage_deviation,
            "load_range": load_range,
            "line_impedance": line_impedance,

            "voltage_unbalance": voltage_unbalance,
            "thd": thd,
            "power_factor": power_factor,

            "hosting_capacity": float(row["hosting_capacity"]),
            "pq_incident": int(row["pq_incident"])
        }

        engineered_data.append(features)

    return engineered_data


if __name__ == "__main__":

    data = load_feeder_data()

    errors = validate_feeder_data(data)

    if errors:
        print("Fix data validation errors first:")
        for error in errors:
            print(error)

    else:
        result = engineer_features(data)

        print("FEATURE ENGINEERING SUCCESSFUL!")
        print("Total feeders:", len(result))

        print("\nFeatures of first feeder:")

        for key, value in result[0].items():
            print(f"{key}: {value}")
