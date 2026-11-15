
from pathlib import Path
import csv
import joblib
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]

MODEL_DIR = BASE_DIR / "models" / "saved"

DATASET_FILE = (
    BASE_DIR / "data" / "processed"
    / "ml_training_dataset.csv"
)


# =========================================
# LOAD BASELINE VALUES
# =========================================

def load_baseline(features):

    with open(
        DATASET_FILE,
        "r",
        newline="",
        encoding="utf-8"
    ) as file:

        rows = list(csv.DictReader(file))

    baseline = {}

    for feature in features:

        values = [
            float(row[feature])
            for row in rows
            if row.get(feature, "") != ""
        ]

        if not values:
            raise ValueError(
                f"No baseline values for {feature}"
            )

        baseline[feature] = float(
            np.median(values)
        )

    return baseline


# =========================================
# LOAD MODELS
# =========================================

def load_model(filename):

    path = MODEL_DIR / filename

    if not path.exists():
        raise FileNotFoundError(path)

    return joblib.load(path)


# =========================================
# EXPLAIN REGRESSION PREDICTION
# =========================================

def explain_regression(peak_load_kw, line_length_km):

    bundle = load_model(
        "hosting_capacity_model.joblib"
    )

    model = bundle["model"]

    features = bundle["features"]

    baseline = load_baseline(features)

    actual = {
        "peak_load_kw": peak_load_kw,
        "line_length_km": line_length_km
    }

    actual_values = np.array([[
        actual[feature] for feature in features
    ]])

    original_prediction = float(
        model.predict(actual_values)[0]
    )

    print("\nREGRESSION EXPLANATION")
    print("=" * 55)

    print(
        "Original predicted capacity:",
        round(original_prediction, 2),
        "kW"
    )

    for feature in features:

        changed = actual.copy()

        changed[feature] = baseline[feature]

        changed_values = np.array([[
            changed[name] for name in features
        ]])

        new_prediction = float(
            model.predict(changed_values)[0]
        )

        difference = (
            original_prediction - new_prediction
        )

        print(f"\nFeature: {feature}")

        print(
            "Actual input:",
            actual[feature]
        )

        print(
            "Dataset median baseline:",
            round(baseline[feature], 3)
        )

        print(
            "Prediction change:",
            round(difference, 3),
            "kW"
        )


# =========================================
# EXPLAIN CLASSIFICATION PREDICTION
# =========================================

def explain_classification(
    peak_load_kw,
    line_length_km,
    existing_solar_kw,
    requested_solar_kw
):

    bundle = load_model(
        "constraint_risk_model.joblib"
    )

    model = bundle["model"]

    features = bundle["features"]

    baseline = load_baseline(features)

    actual = {
        "peak_load_kw": peak_load_kw,
        "line_length_km": line_length_km,
        "existing_solar_kw": existing_solar_kw,
        "requested_solar_kw": requested_solar_kw
    }

    def get_probability(inputs):

        values = np.array([[
            inputs[feature] for feature in features
        ]])

        probabilities = model.predict_proba(values)[0]

        class_index = list(
            model.classes_
        ).index(1)

        return float(probabilities[class_index])

    original_probability = get_probability(actual)

    print("\nCLASSIFICATION EXPLANATION")
    print("=" * 55)

    print(
        "Original violation model score:",
        round(original_probability * 100, 2),
        "%"
    )

    for feature in features:

        changed = actual.copy()

        changed[feature] = baseline[feature]

        new_probability = get_probability(changed)

        difference = (
            original_probability - new_probability
        ) * 100

        print(f"\nFeature: {feature}")

        print(
            "Actual input:",
            actual[feature]
        )

        print(
            "Dataset median baseline:",
            round(baseline[feature], 3)
        )

        print(
            "Score change:",
            round(difference, 3),
            "percentage points"
        )


# =========================================
# TEST EXPLANATIONS
# =========================================

if __name__ == "__main__":

    explain_regression(
        peak_load_kw=300,
        line_length_km=0.2
    )

    explain_classification(
        peak_load_kw=300,
        line_length_km=0.2,
        existing_solar_kw=200,
        requested_solar_kw=100
    )

    print("\nEXPLANATION ANALYSIS COMPLETED!")
