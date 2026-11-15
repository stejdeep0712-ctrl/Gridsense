
import csv
from pathlib import Path

import numpy as np
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    average_precision_score
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
    MODEL_DIR / "constraint_risk_model.joblib"
)


# =========================================
# INPUT FEATURES
# =========================================

FEATURES = [
    "peak_load_kw",
    "line_length_km",
    "existing_solar_kw",
    "requested_solar_kw"
]

TARGET = "constraint_violation"


# =========================================
# LOAD DATASET
# =========================================

def load_dataset():

    if not DATASET_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_FILE}"
        )

    with open(
        DATASET_FILE,
        "r",
        newline="",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)

        required_columns = (
            FEATURES
            + [
                TARGET,
                "feeder_id",
                "power_flow_converged"
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

    X = []
    y = []
    groups = []

    skipped_rows = 0

    for row in rows:

        # Exclude simulations that did not converge.
        if row["power_flow_converged"] != "1":
            skipped_rows += 1
            continue

        try:

            features = [
                float(row[column])
                for column in FEATURES
            ]

            label = int(row[TARGET])

            feeder_id = row["feeder_id"].strip()

        except (ValueError, TypeError, KeyError):
            skipped_rows += 1
            continue

        if not feeder_id:
            skipped_rows += 1
            continue

        if label not in (0, 1):
            skipped_rows += 1
            continue

        if not np.all(np.isfinite(features)):
            skipped_rows += 1
            continue

        X.append(features)
        y.append(label)
        groups.append(feeder_id)

    if not X:
        raise ValueError(
            "No valid training records found."
        )

    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    groups = np.asarray(groups)

    if len(np.unique(y)) != 2:
        raise ValueError(
            "Dataset must contain both class 0 and class 1."
        )

    print("Skipped invalid/non-converged rows:", skipped_rows)

    return X, y, groups


# =========================================
# FEATURE RANGE METADATA
# =========================================

def calculate_feature_ranges(X):

    ranges = {}

    for index, feature in enumerate(FEATURES):

        ranges[feature] = {
            "min": float(np.min(X[:, index])),
            "max": float(np.max(X[:, index])),
            "mean": float(np.mean(X[:, index]))
        }

    return ranges


# =========================================
# GROUPED TRAIN / TEST SPLIT
# =========================================

def create_grouped_split(X, y, groups):

    splitter = GroupShuffleSplit(
        n_splits=200,
        test_size=0.25,
        random_state=42
    )

    for train_idx, test_idx in splitter.split(
        X, y, groups
    ):

        if (
            len(np.unique(y[train_idx])) == 2
            and len(np.unique(y[test_idx])) == 2
        ):
            return train_idx, test_idx

    raise ValueError(
        "Could not find a feeder-independent split "
        "containing both classes in train and test. "
        "Generate more diverse configurations."
    )


# =========================================
# TRAIN CLASSIFICATION MODEL
# =========================================

def train_classifier():

    X, y, groups = load_dataset()

    print("=" * 60)
    print("       ENGINEERING CONSTRAINT CLASSIFIER")
    print("=" * 60)

    unique_feeders = np.unique(groups)

    print("\nDATASET INFORMATION")

    print("Total valid records:", len(y))
    print("Unique feeder groups:", len(unique_feeders))

    print("\nCLASS DISTRIBUTION")

    class_0_count = int(np.sum(y == 0))
    class_1_count = int(np.sum(y == 1))

    print("Class 0:", class_0_count)
    print("Class 1:", class_1_count)

    if len(unique_feeders) < 10:

        print(
            "\nWARNING: Very few feeder configurations. "
            "Evaluation may be uncertain."
        )

    if class_1_count < 10:

        print(
            "\nWARNING: Very few positive violation records."
        )

    # =====================================
    # FEATURE RANGES
    # =====================================

    feature_ranges = calculate_feature_ranges(X)

    print("\nFEATURE RANGES")

    for feature, values in feature_ranges.items():

        print(
            f"{feature}: "
            f"min={values['min']:.2f}, "
            f"max={values['max']:.2f}, "
            f"mean={values['mean']:.2f}"
        )

    # =====================================
    # GROUPED DATA SPLIT
    # =====================================

    train_idx, test_idx = create_grouped_split(
        X, y, groups
    )

    train_feeders = set(groups[train_idx])
    test_feeders = set(groups[test_idx])

    # Confirm no feeder leakage.
    assert train_feeders.isdisjoint(test_feeders)

    X_train = X[train_idx]
    X_test = X[test_idx]

    y_train = y[train_idx]
    y_test = y[test_idx]

    print("\nDATA SPLIT")

    print("Training records:", len(train_idx))
    print("Testing records:", len(test_idx))

    print("Training feeder groups:", len(train_feeders))
    print("Testing feeder groups:", len(test_feeders))

    print(
        "Feeder overlap:",
        len(train_feeders.intersection(test_feeders))
    )

    print(
        "Training class distribution:",
        np.bincount(y_train, minlength=2)
    )

    print(
        "Testing class distribution:",
        np.bincount(y_test, minlength=2)
    )

    # =====================================
    # RANDOM FOREST CLASSIFIER
    # =====================================

    model = RandomForestClassifier(
        n_estimators=300,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    probabilities = model.predict_proba(X_test)[:, 1]

    # =====================================
    # MODEL EVALUATION
    # =====================================

    accuracy = accuracy_score(
        y_test, predictions
    )

    balanced_accuracy = balanced_accuracy_score(
        y_test, predictions
    )

    precision = precision_score(
        y_test,
        predictions,
        zero_division=0
    )

    recall = recall_score(
        y_test,
        predictions,
        zero_division=0
    )

    f1 = f1_score(
        y_test,
        predictions,
        zero_division=0
    )

    pr_auc = average_precision_score(
        y_test, probabilities
    )

    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=[0, 1]
    )

    print("\nMODEL PERFORMANCE")

    print("Accuracy:", round(accuracy, 4))
    print("Balanced accuracy:", round(balanced_accuracy, 4))
    print("Precision:", round(precision, 4))
    print("Recall:", round(recall, 4))
    print("F1-score:", round(f1, 4))
    print("PR-AUC:", round(pr_auc, 4))

    print("\nCONFUSION MATRIX")

    print(matrix)

    print("\nCLASSIFICATION REPORT")

    print(
        classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=[
                "No configured violation",
                "Configured violation"
            ],
            zero_division=0
        )
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
    # SAVE MODEL
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
            "1 = at least one configured voltage, "
            "transformer or line constraint violation "
            "in the OpenDSS simulation."
        ),

        "training_feeders": sorted(train_feeders),

        "testing_feeders": sorted(test_feeders),

        "feature_ranges": feature_ranges,

        "feature_importance": feature_importance,

        "evaluation": {

            "accuracy": float(accuracy),

            "balanced_accuracy": float(
                balanced_accuracy
            ),

            "precision": float(precision),

            "recall": float(recall),

            "f1_score": float(f1),

            "pr_auc": float(pr_auc),

            "confusion_matrix": matrix.tolist()

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
        "\nIMPORTANT: The model uses parameterized "
        "OpenDSS simulation data from a demonstration "
        "network. It is not validated on independent "
        "real-world feeders or historical incidents."
    )


if __name__ == "__main__":

    train_classifier()
