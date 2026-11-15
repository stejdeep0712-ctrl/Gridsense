
import csv
import math
from collections import Counter
from pathlib import Path

import numpy as np
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


# =========================================
# PROJECT PATHS
# =========================================

BASE_DIR = Path(__file__).resolve().parents[1]

DATASET_FILE = (
    BASE_DIR / "data" / "processed"
    / "ml_training_dataset.csv"
)

MODEL_DIR = BASE_DIR / "models" / "saved"

MODEL_FILE = (
    MODEL_DIR / "hosting_capacity_model.joblib"
)


# =========================================
# MODEL CONFIGURATION
# =========================================

FEATURES = [
    "peak_load_kw",
    "line_length_km",
    "existing_solar_kw"
]

TARGET = "hosting_capacity_kw"

MAX_TESTED_ADDITIONAL_KW = 800

SOLAR_STEP_KW = 25

MINIMUM_CONFIGURATIONS = 20


# =========================================
# LOAD AND VALIDATE FEEDER RECORDS
# =========================================

def load_feeder_records():

    if not DATASET_FILE.exists():
        raise FileNotFoundError(DATASET_FILE)

    with open(
        DATASET_FILE,
        newline="",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)

        required_columns = (
            FEATURES
            + [
                TARGET,
                "feeder_id",
                "requested_solar_kw",
                "power_flow_converged",
                "constraint_violation"
            ]
        )

        missing_columns = [
            column
            for column in required_columns
            if column not in (reader.fieldnames or [])
        ]

        if missing_columns:
            raise ValueError(
                f"Missing dataset columns: {missing_columns}"
            )

        rows = list(reader)

    if not rows:
        raise ValueError("Dataset is empty.")

    grouped = {}

    for row in rows:

        feeder_id = row["feeder_id"].strip()

        grouped.setdefault(
            feeder_id, []
        ).append(row)

    records = []

    excluded = Counter()

    expected_levels = list(
        range(
            0,
            MAX_TESTED_ADDITIONAL_KW + 1,
            SOLAR_STEP_KW
        )
    )

    # =====================================
    # VALIDATE EACH FEEDER SWEEP
    # =====================================

    for feeder_id, feeder_rows in grouped.items():

        try:

            feeder_rows.sort(
                key=lambda row: float(
                    row["requested_solar_kw"]
                )
            )

            levels = [
                float(row["requested_solar_kw"])
                for row in feeder_rows
            ]

        except (ValueError, TypeError):

            excluded["invalid_solar_levels"] += 1
            continue

        # ---------------------------------
        # REQUIRE COMPLETE 0-800 KW SWEEP
        # ---------------------------------

        if levels != expected_levels:

            excluded["incomplete_sweep"] += 1
            continue

        # ---------------------------------
        # CHECK CONVERGENCE VALUES
        # ---------------------------------

        convergence_values = [
            row["power_flow_converged"]
            for row in feeder_rows
        ]

        if any(
            value not in ("0", "1")
            for value in convergence_values
        ):

            excluded["invalid_convergence"] += 1
            continue

        # ---------------------------------
        # CHECK LABEL VALUES
        # ---------------------------------

        try:

            violations = [
                int(row["constraint_violation"])
                for row in feeder_rows
            ]

        except (ValueError, TypeError):

            excluded["invalid_labels"] += 1
            continue

        if any(
            value not in (0, 1)
            for value in violations
        ):

            excluded["invalid_labels"] += 1
            continue

        # ---------------------------------
        # BASELINE MUST PASS
        # ---------------------------------

        if (
            feeder_rows[0]["power_flow_converged"] != "1"
            or violations[0] != 0
        ):

            excluded["baseline_failure"] += 1
            continue

        # ---------------------------------
        # FIND FIRST FAILURE
        # ---------------------------------

        first_failure = next(
            (
                index
                for index, value in enumerate(violations)
                if value == 1
            ),
            None
        )

        # ---------------------------------
        # EXCLUDE RIGHT-CENSORED CONFIGS
        # ---------------------------------

        if first_failure is None:

            excluded["right_censored_above_800kw"] += 1
            continue

        # ---------------------------------
        # REQUIRE CLEAN PASS-TO-FAIL BOUNDARY
        # ---------------------------------

        if any(
            value == 0
            for value in violations[first_failure:]
        ):

            excluded["non_monotonic_sweep"] += 1
            continue

        # ---------------------------------
        # GET LAST PASSING CAPACITY
        # ---------------------------------

        last_pass = float(
            feeder_rows[first_failure - 1][
                "requested_solar_kw"
            ]
        )

        # ---------------------------------
        # VALIDATE REGRESSION TARGET
        # ---------------------------------

        try:

            stored_targets = [
                float(row[TARGET])
                for row in feeder_rows
            ]

        except (ValueError, TypeError):

            excluded["invalid_target"] += 1
            continue

        if not all(
            math.isfinite(value)
            for value in stored_targets
        ):

            excluded["invalid_target"] += 1
            continue

        # The target should be consistent across
        # every row belonging to this feeder.
        if not all(
            value == stored_targets[0]
            for value in stored_targets
        ):

            excluded["inconsistent_target"] += 1
            continue

        # The stored target must match the
        # measured last passing solar level.
        if not math.isclose(
            stored_targets[0],
            last_pass,
            abs_tol=1e-6
        ):

            excluded["target_boundary_mismatch"] += 1
            continue

        # ---------------------------------
        # EXTRACT BASELINE FEATURES
        # ---------------------------------

        try:

            features = [
                float(feeder_rows[0][name])
                for name in FEATURES
            ]

        except (ValueError, TypeError):

            excluded["invalid_features"] += 1
            continue

        if not all(
            math.isfinite(value)
            for value in features
        ):

            excluded["invalid_features"] += 1
            continue

        records.append({

            "feeder_id": feeder_id,

            "features": features,

            "target": last_pass

        })

    return records, excluded


# =========================================
# CREATE GROUPED TRAIN / TEST SPLIT
# =========================================

def create_grouped_split(X, y, groups):

    splitter = GroupShuffleSplit(
        n_splits=200,
        test_size=0.25,
        random_state=42
    )

    for train_idx, test_idx in splitter.split(
        X,
        y,
        groups
    ):

        train_targets = np.unique(y[train_idx])

        test_targets = np.unique(y[test_idx])

        # Require sufficient target variation
        # for a meaningful regression evaluation.
        if (
            len(train_targets) >= 3
            and len(test_targets) >= 2
        ):

            return train_idx, test_idx

    raise ValueError(
        "Could not find a grouped train/test split "
        "with sufficient target variation. "
        "Generate more diverse configurations."
    )


# =========================================
# FEATURE RANGE METADATA
# =========================================

def calculate_feature_ranges(X):

    ranges = {}

    for index, name in enumerate(FEATURES):

        ranges[name] = {

            "min": float(np.min(X[:, index])),

            "max": float(np.max(X[:, index])),

            "mean": float(np.mean(X[:, index]))

        }

    return ranges


# =========================================
# TRAIN REGRESSION MODEL
# =========================================

def train_regression_model():

    records, excluded = load_feeder_records()

    print("=" * 65)

    print(
        "       GRIDSENSE HOSTING CAPACITY REGRESSION"
    )

    print("=" * 65)

    print(
        "\nEligible feeder configurations:",
        len(records)
    )

    print(
        "Excluded configurations:",
        dict(excluded)
    )

    if len(records) < MINIMUM_CONFIGURATIONS:

        raise ValueError(
            "Too few eligible feeder configurations. "
            "At least 20 are required."
        )

    # =====================================
    # PREPARE TRAINING ARRAYS
    # =====================================

    X = np.asarray(
        [record["features"] for record in records],
        dtype=float
    )

    y = np.asarray(
        [record["target"] for record in records],
        dtype=float
    )

    feeder_ids = np.asarray(
        [record["feeder_id"] for record in records]
    )

    print(
        "\nDistinct target values:",
        sorted(set(y.tolist()))
    )

    print(
        "Minimum hosting capacity:",
        float(y.min()),
        "kW"
    )

    print(
        "Maximum hosting capacity:",
        float(y.max()),
        "kW"
    )

    if len(np.unique(y)) < 3:

        raise ValueError(
            "Insufficient hosting-capacity target variation."
        )

    # =====================================
    # FEATURE RANGES
    # =====================================

    feature_ranges = calculate_feature_ranges(X)

    print("\nFEATURE RANGES")

    for name, values in feature_ranges.items():

        print(
            f"{name}: "
            f"min={values['min']:.2f}, "
            f"max={values['max']:.2f}, "
            f"mean={values['mean']:.2f}"
        )

    # =====================================
    # GROUPED TRAIN / TEST SPLIT
    # =====================================

    train_idx, test_idx = create_grouped_split(
        X,
        y,
        feeder_ids
    )

    train_feeders = set(feeder_ids[train_idx])

    test_feeders = set(feeder_ids[test_idx])

    assert train_feeders.isdisjoint(test_feeders)

    X_train = X[train_idx]

    X_test = X[test_idx]

    y_train = y[train_idx]

    y_test = y[test_idx]

    print("\nDATA SPLIT")

    print(
        "Training configurations:",
        len(train_idx)
    )

    print(
        "Testing configurations:",
        len(test_idx)
    )

    print(
        "Training feeder groups:",
        len(train_feeders)
    )

    print(
        "Testing feeder groups:",
        len(test_feeders)
    )

    print(
        "Feeder overlap:",
        len(train_feeders.intersection(test_feeders))
    )

    print(
        "Training target range:",
        float(y_train.min()),
        "to",
        float(y_train.max()),
        "kW"
    )

    print(
        "Testing target range:",
        float(y_test.min()),
        "to",
        float(y_test.max()),
        "kW"
    )

    # =====================================
    # RANDOM FOREST REGRESSOR
    # =====================================

    model = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=2,
        max_features=1.0,
        random_state=42,
        n_jobs=-1
    )

    model.fit(
        X_train,
        y_train
    )

    predictions = model.predict(X_test)

    # =====================================
    # EVALUATION
    # =====================================

    mae = mean_absolute_error(
        y_test,
        predictions
    )

    rmse = math.sqrt(
        mean_squared_error(
            y_test,
            predictions
        )
    )

    r2 = r2_score(
        y_test,
        predictions
    )

    print("\nREGRESSION RESULTS")

    print(
        "MAE:",
        round(mae, 3),
        "kW"
    )

    print(
        "RMSE:",
        round(rmse, 3),
        "kW"
    )

    print(
        "R2:",
        round(r2, 4)
    )

    if r2 < 0:

        print(
            "\nWARNING: Negative R2 indicates "
            "poor test-set generalization."
        )

    # =====================================
    # FEATURE IMPORTANCE
    # =====================================

    feature_importance = {}

    print("\nFEATURE IMPORTANCE")

    for name, importance in zip(
        FEATURES,
        model.feature_importances_
    ):

        feature_importance[name] = float(importance)

        print(
            f"{name}: {importance * 100:.2f}%"
        )

    # =====================================
    # TEST CONFIGURATION PREDICTIONS
    # =====================================

    print("\nTEST CONFIGURATION PREDICTIONS")

    for idx, prediction in zip(
        test_idx,
        predictions
    ):

        print(
            f"{feeder_ids[idx]} | "
            f"Actual: {y[idx]:.1f} kW | "
            f"Predicted: {prediction:.1f} kW"
        )

    # =====================================
    # SAVE TRAINED MODEL
    # =====================================

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    model_bundle = {

        "model": model,

        "features": FEATURES,

        "target": TARGET,

        "target_definition": (
            "Last passing additional solar capacity "
            "before the first configured constraint "
            "violation, using a 25 kW sweep. "
            "Right-censored configurations are excluded."
        ),

        "maximum_tested_additional_kw": (
            MAX_TESTED_ADDITIONAL_KW
        ),

        "solar_step_kw": SOLAR_STEP_KW,

        "training_feeders": sorted(train_feeders),

        "testing_feeders": sorted(test_feeders),

        "feature_ranges": feature_ranges,

        "feature_importance": feature_importance,

        "evaluation": {

            "mae_kw": float(mae),

            "rmse_kw": float(rmse),

            "r2": float(r2)

        },

        "validation_method": (
            "GroupShuffleSplit by feeder_id"
        ),

        "research_only": True

    }

    joblib.dump(
        model_bundle,
        MODEL_FILE
    )

    print("\nMODEL SAVED SUCCESSFULLY!")

    print(MODEL_FILE)

    print(
        "\nIMPORTANT: This model uses parameterized "
        "OpenDSS simulations of a demonstration network. "
        "It has not been validated on independent "
        "real-world feeders."
    )


# =========================================
# MAIN
# =========================================

if __name__ == "__main__":

    train_regression_model()
