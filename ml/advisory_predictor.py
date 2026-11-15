
from pathlib import Path

import numpy as np
import joblib


# =========================================
# MODEL PATHS
# =========================================

BASE_DIR = Path(__file__).resolve().parents[1]

MODEL_DIR = BASE_DIR / "models" / "saved"

REGRESSION_FILE = (
    MODEL_DIR / "hosting_capacity_model.joblib"
)

CLASSIFICATION_FILE = (
    MODEL_DIR / "constraint_risk_model.joblib"
)


# =========================================
# EXPECTED MODEL FEATURES
# =========================================

REGRESSION_FEATURES = [
    "peak_load_kw",
    "line_length_km",
    "existing_solar_kw"
]

CLASSIFICATION_FEATURES = [
    "peak_load_kw",
    "line_length_km",
    "existing_solar_kw",
    "requested_solar_kw"
]


# =========================================
# LOAD TRAINED MODELS
# =========================================

def load_models():

    if not REGRESSION_FILE.exists():

        raise FileNotFoundError(
            "Regression model not found. Train it first."
        )

    if not CLASSIFICATION_FILE.exists():

        raise FileNotFoundError(
            "Classification model not found. Train it first."
        )

    regression_bundle = joblib.load(
        REGRESSION_FILE
    )

    classification_bundle = joblib.load(
        CLASSIFICATION_FILE
    )

    # -------------------------------------
    # VERIFY MODEL FEATURE COMPATIBILITY
    # -------------------------------------

    if regression_bundle.get("features") != REGRESSION_FEATURES:

        raise ValueError(
            "Regression model features do not match "
            "the advisory predictor. Retrain the model."
        )

    if classification_bundle.get("features") != CLASSIFICATION_FEATURES:

        raise ValueError(
            "Classification model features do not match "
            "the advisory predictor. Retrain the model."
        )

    return regression_bundle, classification_bundle


# =========================================
# CHECK TRAINING FEATURE RANGES
# =========================================

def check_feature_ranges(
    input_values,
    feature_ranges,
    model_name
):

    warnings = []

    for feature, value in input_values.items():

        if feature not in feature_ranges:

            warnings.append(
                f"{model_name}: Training range unavailable "
                f"for {feature}."
            )

            continue

        minimum = feature_ranges[feature]["min"]

        maximum = feature_ranges[feature]["max"]

        if value < minimum or value > maximum:

            warnings.append(
                f"{model_name}: {feature}={value} is outside "
                f"the training range ({minimum} to {maximum}). "
                f"Prediction may be unreliable."
            )

    return warnings


# =========================================
# AI ADVISORY PREDICTION
# =========================================

def generate_ai_advisory(
    peak_load_kw,
    line_length_km,
    existing_solar_kw,
    requested_solar_kw
):

    # -------------------------------------
    # VALIDATE INPUTS
    # -------------------------------------

    input_values = {

        "peak_load_kw": peak_load_kw,

        "line_length_km": line_length_km,

        "existing_solar_kw": existing_solar_kw,

        "requested_solar_kw": requested_solar_kw

    }

    try:

        input_values = {
            name: float(value)
            for name, value in input_values.items()
        }

    except (ValueError, TypeError):

        raise ValueError(
            "All input values must be valid numbers."
        )

    values = list(input_values.values())

    if not all(
        np.isfinite(value) and value >= 0
        for value in values
    ):

        raise ValueError(
            "All input values must be finite and non-negative."
        )

    if (
        input_values["peak_load_kw"] <= 0
        or input_values["line_length_km"] <= 0
    ):

        raise ValueError(
            "Peak load and line length must be greater than zero."
        )

    # -------------------------------------
    # LOAD MODELS
    # -------------------------------------

    regression_bundle, classification_bundle = load_models()

    regression_model = regression_bundle["model"]

    classifier = classification_bundle["model"]

    # =====================================
    # REGRESSION PREDICTION
    # =====================================

    regression_input = {

        "peak_load_kw": input_values["peak_load_kw"],

        "line_length_km": input_values["line_length_km"],

        "existing_solar_kw": input_values["existing_solar_kw"]

    }

    regression_features = np.array([[
        regression_input[feature]
        for feature in REGRESSION_FEATURES
    ]], dtype=float)

    predicted_capacity = float(
        regression_model.predict(
            regression_features
        )[0]
    )

    # =====================================
    # CLASSIFICATION PREDICTION
    # =====================================

    classification_input = {

        "peak_load_kw": input_values["peak_load_kw"],

        "line_length_km": input_values["line_length_km"],

        "existing_solar_kw": input_values["existing_solar_kw"],

        "requested_solar_kw": input_values["requested_solar_kw"]

    }

    classification_features = np.array([[
        classification_input[feature]
        for feature in CLASSIFICATION_FEATURES
    ]], dtype=float)

    predicted_class = int(
        classifier.predict(
            classification_features
        )[0]
    )

    class_probabilities = classifier.predict_proba(
        classification_features
    )[0]

    class_one_index = list(
        classifier.classes_
    ).index(1)

    violation_model_score = float(
        class_probabilities[class_one_index]
    )

    # =====================================
    # FEATURE RANGE VALIDATION
    # =====================================

    range_warnings = []

    range_warnings.extend(
        check_feature_ranges(
            regression_input,
            regression_bundle.get("feature_ranges", {}),
            "Regression model"
        )
    )

    range_warnings.extend(
        check_feature_ranges(
            classification_input,
            classification_bundle.get("feature_ranges", {}),
            "Classification model"
        )
    )

    # =====================================
    # COMBINED ADVISORY
    # =====================================

    proposed_total_solar = (
        input_values["existing_solar_kw"]
        + input_values["requested_solar_kw"]
    )

    estimated_headroom = max(
        0.0,
        predicted_capacity
    )

    if predicted_class == 1:

        status = "HIGHER_SIMULATED_RISK"

        explanation = (
            "The classification model predicts a configured "
            "engineering constraint violation. Further "
            "engineering investigation is required."
        )

    elif input_values["requested_solar_kw"] > estimated_headroom:

        status = "ABOVE_PREDICTED_CAPACITY"

        explanation = (
            "The requested additional solar capacity exceeds "
            "the regression model's estimated hosting capacity."
        )

    else:

        status = "PRELIMINARY_MODEL_SCREENING_PASS"

        explanation = (
            "The request is within the regression model's "
            "estimated capacity and the classifier predicts "
            "no configured constraint violation. This is "
            "not an engineering approval."
        )

    # =====================================
    # LIMITATIONS
    # =====================================

    limitations = [

        "Models use parameterized OpenDSS simulation data.",

        "Both models use configurations of one demonstration "
        "network topology.",

        "Predictions are preliminary research outputs.",

        "Historical power-quality incidents are not predicted.",

        "Classifier scores are not calibrated real-world "
        "violation probabilities.",

        "Inputs outside the training range may produce "
        "unreliable predictions.",

        "OpenDSS engineering validation is still required.",

        "This result is not a utility connection approval."

    ]

    if range_warnings:

        limitations.append(
            "One or more input values are outside the "
            "model training ranges."
        )

    # =====================================
    # FINAL RESPONSE
    # =====================================

    return {

        "status": status,

        "inputs": {

            "peak_load_kw": input_values["peak_load_kw"],

            "line_length_km": input_values["line_length_km"],

            "existing_solar_kw": input_values["existing_solar_kw"],

            "requested_solar_kw": input_values["requested_solar_kw"],

            "proposed_total_solar_kw": proposed_total_solar

        },

        "regression_prediction": {

            "estimated_additional_hosting_capacity_kw":
                round(predicted_capacity, 2)

        },

        "classification_prediction": {

            "predicted_class": predicted_class,

            "configured_violation_model_score_percent":
                round(violation_model_score * 100, 2)

        },

        "range_validation": {

            "within_training_ranges": len(range_warnings) == 0,

            "warnings": range_warnings

        },

        "explanation": explanation,

        "limitations": limitations

    }


# =========================================
# TEST THE ADVISORY SERVICE
# =========================================

if __name__ == "__main__":

    result = generate_ai_advisory(

        peak_load_kw=260,

        line_length_km=0.3,

        existing_solar_kw=150,

        requested_solar_kw=100

    )

    print("=" * 60)

    print("             GRIDSENSE AI ADVISORY")

    print("=" * 60)

    for section, value in result.items():

        print(f"\n{section.upper()}:")

        print(value)
