
import csv
from pathlib import Path

import joblib
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score
)


# =========================================
# PATH CONFIGURATION
# =========================================

BASE_DIR = Path(__file__).resolve().parents[1]

DATASET_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "pq_multifeeder_dataset.csv"
)

MODEL_DIR = BASE_DIR / "models" / "saved"

MODEL_FILE = (
    MODEL_DIR / "pq_screening_model.joblib"
)


# =========================================
# MODEL CONFIGURATION
# =========================================

FEATURES = [
    "line_length_km",
    "line_r1",
    "line_x1",
    "phase_a_load_kw",
    "phase_b_load_kw",
    "phase_c_load_kw"
]

TARGET = "pq_limit_exceeded"

GROUP_COLUMN = "feeder_id"

VUF_THRESHOLD = 2.0

BASELINE_THRESHOLD = 0.50

THRESHOLDS_TO_TEST = [
    0.10,
    0.15,
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.45,
    0.50
]


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

        rows = list(csv.DictReader(file))

    if not rows:

        raise ValueError(
            "Dataset is empty."
        )

    required_columns = (
        FEATURES
        + [
            TARGET,
            GROUP_COLUMN,
            "power_flow_converged"
        ]
    )

    for column in required_columns:

        if column not in rows[0]:

            raise ValueError(
                f"Required column missing: {column}"
            )

    # Keep only successfully converged simulations

    rows = [
        row for row in rows
        if row["power_flow_converged"] == "1"
    ]

    if not rows:

        raise ValueError(
            "No converged scenarios found."
        )

    return rows


# =========================================
# PREPARE DATA
# =========================================

def prepare_data(rows):

    X = np.array(
        [
            [
                float(row[feature])
                for feature in FEATURES
            ]
            for row in rows
        ],
        dtype=float
    )

    y = np.array(
        [
            int(row[TARGET])
            for row in rows
        ],
        dtype=int
    )

    groups = np.array(
        [
            row[GROUP_COLUMN]
            for row in rows
        ]
    )

    if not np.isfinite(X).all():

        raise ValueError(
            "Dataset contains invalid feature values."
        )

    if not set(np.unique(y)).issubset({0, 1}):

        raise ValueError(
            "Target must contain only class 0 and class 1."
        )

    if len(np.unique(y)) != 2:

        raise ValueError(
            "Dataset must contain both target classes."
        )

    if len(np.unique(groups)) < 2:

        raise ValueError(
            "At least two feeder configurations are required."
        )

    return X, y, groups


# =========================================
# RANDOM FOREST MODEL
# =========================================

def create_model():

    return RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )


# =========================================
# LEAVE-ONE-FEEDER-OUT VALIDATION
# =========================================

def run_lofo_validation(X, y, groups):

    logo = LeaveOneGroupOut()

    oof_probabilities = np.full(
        shape=len(y),
        fill_value=np.nan,
        dtype=float
    )

    fold_results = []

    print("\n==========================================")
    print(" LEAVE-ONE-FEEDER-OUT VALIDATION")
    print("==========================================")

    for fold, (train_idx, test_idx) in enumerate(
        logo.split(X, y, groups),
        start=1
    ):

        X_train = X[train_idx]
        X_test = X[test_idx]

        y_train = y[train_idx]
        y_test = y[test_idx]

        train_groups = np.unique(
            groups[train_idx]
        )

        test_groups = np.unique(
            groups[test_idx]
        )

        # Check both classes exist in training data

        if len(np.unique(y_train)) != 2:

            raise ValueError(
                f"Fold {fold}: training data does not "
                "contain both classes."
            )

        # Train model

        model = create_model()

        model.fit(
            X_train,
            y_train
        )

        # Obtain class 1 probabilities

        class_1_index = list(
            model.classes_
        ).index(1)

        probabilities = model.predict_proba(
            X_test
        )[:, class_1_index]

        oof_probabilities[test_idx] = probabilities

        # Baseline predictions

        predictions = (
            probabilities >= BASELINE_THRESHOLD
        ).astype(int)

        accuracy = accuracy_score(
            y_test,
            predictions
        )

        class_1_f1 = f1_score(
            y_test,
            predictions,
            pos_label=1,
            zero_division=0
        )

        fold_results.append({

            "feeder": str(test_groups[0]),

            "samples": int(len(test_idx)),

            "accuracy": float(accuracy),

            "class_1_f1": float(class_1_f1),

            "actual_class_0": int(
                np.sum(y_test == 0)
            ),

            "actual_class_1": int(
                np.sum(y_test == 1)
            )

        })

        print(f"\nFOLD {fold}")

        print("------------------------------------------")

        print(
            "Testing feeder:",
            test_groups
        )

        print(
            "Training feeders:",
            train_groups
        )

        print(
            "Testing samples:",
            len(test_idx)
        )

        print(
            "Class 0:",
            int(np.sum(y_test == 0))
        )

        print(
            "Class 1:",
            int(np.sum(y_test == 1))
        )

        print(
            "Accuracy:",
            round(accuracy, 4)
        )

        print(
            "Class 1 F1:",
            round(class_1_f1, 4)
        )

        print("Confusion Matrix:")

        print(
            confusion_matrix(
                y_test,
                predictions,
                labels=[0, 1]
            )
        )

    if np.isnan(oof_probabilities).any():

        raise RuntimeError(
            "Some samples did not receive out-of-fold predictions."
        )

    return (
        oof_probabilities,
        fold_results
    )


# =========================================
# THRESHOLD ANALYSIS
# =========================================

def evaluate_thresholds(
    y_true,
    probabilities
):

    print("\n==========================================")
    print(" CLASS 1 THRESHOLD ANALYSIS")
    print("==========================================")

    results = []

    for threshold in THRESHOLDS_TO_TEST:

        predictions = (
            probabilities >= threshold
        ).astype(int)

        precision = precision_score(
            y_true,
            predictions,
            pos_label=1,
            zero_division=0
        )

        recall = recall_score(
            y_true,
            predictions,
            pos_label=1,
            zero_division=0
        )

        f1 = f1_score(
            y_true,
            predictions,
            pos_label=1,
            zero_division=0
        )

        accuracy = accuracy_score(
            y_true,
            predictions
        )

        false_negatives = int(
            np.sum(
                (y_true == 1) &
                (predictions == 0)
            )
        )

        false_positives = int(
            np.sum(
                (y_true == 0) &
                (predictions == 1)
            )
        )

        results.append({

            "threshold": float(threshold),

            "accuracy": float(accuracy),

            "precision": float(precision),

            "recall": float(recall),

            "f1": float(f1),

            "false_negatives": false_negatives,

            "false_positives": false_positives

        })

        print(
            f"Threshold: {threshold:.2f} | "
            f"Accuracy: {accuracy:.4f} | "
            f"Precision: {precision:.4f} | "
            f"Recall: {recall:.4f} | "
            f"F1: {f1:.4f} | "
            f"FN: {false_negatives} | "
            f"FP: {false_positives}"
        )

    return results


# =========================================
# OVERALL EVALUATION
# =========================================

def evaluate_model(
    y_true,
    probabilities,
    threshold
):

    predictions = (
        probabilities >= threshold
    ).astype(int)

    accuracy = accuracy_score(
        y_true,
        predictions
    )

    balanced_accuracy = balanced_accuracy_score(
        y_true,
        predictions
    )

    precision = precision_score(
        y_true,
        predictions,
        zero_division=0
    )

    recall = recall_score(
        y_true,
        predictions,
        zero_division=0
    )

    f1 = f1_score(
        y_true,
        predictions,
        zero_division=0
    )

    print("\n==========================================")
    print(" OVERALL OUT-OF-FOLD EVALUATION")
    print("==========================================")

    print("Decision threshold:", threshold)

    print(
        "Accuracy:",
        round(accuracy, 4)
    )

    print(
        "Balanced Accuracy:",
        round(balanced_accuracy, 4)
    )

    print(
        "Class 1 Precision:",
        round(precision, 4)
    )

    print(
        "Class 1 Recall:",
        round(recall, 4)
    )

    print(
        "Class 1 F1 Score:",
        round(f1, 4)
    )

    print("\nCombined Confusion Matrix:")

    matrix = confusion_matrix(
        y_true,
        predictions,
        labels=[0, 1]
    )

    print(matrix)

    print("\nCombined Classification Report:")

    print(
        classification_report(
            y_true,
            predictions,
            labels=[0, 1],
            target_names=[
                "Within VUF limit",
                "VUF limit exceeded"
            ],
            zero_division=0
        )
    )

    return {
        "accuracy": float(accuracy),
        "balanced_accuracy": float(balanced_accuracy),
        "class_1_precision": float(precision),
        "class_1_recall": float(recall),
        "class_1_f1": float(f1),
        "confusion_matrix": matrix.tolist()
    }


# =========================================
# MAIN TRAINING FUNCTION
# =========================================

def train_model():

    print("\n==========================================")
    print(" GRIDSENSE PQ CLASSIFICATION MODEL")
    print("==========================================")

    # Load dataset

    rows = load_dataset()

    # Prepare data

    X, y, groups = prepare_data(rows)

    unique_groups = np.unique(groups)

    print("\nDATASET INFORMATION")

    print("------------------------------------------")

    print(
        "Total samples:",
        len(y)
    )

    print(
        "Class 0:",
        int(np.sum(y == 0))
    )

    print(
        "Class 1:",
        int(np.sum(y == 1))
    )

    print(
        "Feeder configurations:",
        len(unique_groups)
    )

    for feeder in unique_groups:

        mask = groups == feeder

        print(f"\n{feeder}")

        print(
            "Samples:",
            int(np.sum(mask))
        )

        print(
            "Class 0:",
            int(np.sum(y[mask] == 0))
        )

        print(
            "Class 1:",
            int(np.sum(y[mask] == 1))
        )

    # =====================================
    # LOFO VALIDATION
    # =====================================

    (
        oof_probabilities,
        fold_results
    ) = run_lofo_validation(
        X,
        y,
        groups
    )

    # =====================================
    # BASELINE EVALUATION
    # =====================================

    baseline_evaluation = evaluate_model(
        y,
        oof_probabilities,
        BASELINE_THRESHOLD
    )

    # =====================================
    # THRESHOLD COMPARISON
    # =====================================

    threshold_results = evaluate_thresholds(
        y,
        oof_probabilities
    )

    # =====================================
    # FEEDER-WISE SUMMARY
    # =====================================

    print("\n==========================================")
    print(" FEEDER-WISE VALIDATION SUMMARY")
    print("==========================================")

    for result in fold_results:

        print(
            f"{result['feeder']} | "
            f"Samples: {result['samples']} | "
            f"Accuracy: {result['accuracy']:.4f} | "
            f"Class 1 F1: {result['class_1_f1']:.4f}"
        )

    # =====================================
    # TRAIN FINAL DEPLOYMENT MODEL
    # =====================================

    print("\nTraining final deployment model...")

    final_model = create_model()

    final_model.fit(
        X,
        y
    )

    # =====================================
    # FEATURE IMPORTANCE
    # =====================================

    print("\n==========================================")
    print(" FEATURE IMPORTANCE")
    print("==========================================")

    importances = final_model.feature_importances_

    for name, importance in sorted(
        zip(FEATURES, importances),
        key=lambda item: item[1],
        reverse=True
    ):

        print(
            f"{name}: {importance:.4f}"
        )

    # =====================================
    # SAVE MODEL BUNDLE
    # =====================================

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    model_bundle = {

        "model": final_model,

        "features": FEATURES,

        "target": TARGET,

        "screening_threshold_percent": VUF_THRESHOLD,

        "decision_threshold": BASELINE_THRESHOLD,

        "dataset_type": (
            "simulated_vuf_threshold_exceedance"
        ),

        "dataset_file": (
            "pq_multifeeder_dataset.csv"
        ),

        "validation_method": (
            "LeaveOneGroupOut by feeder_id"
        ),

        "training_feeders": unique_groups.tolist(),

        "testing_feeders": (
            "Every feeder configuration held out once"
        ),

        "evaluation": baseline_evaluation,

        "fold_results": fold_results,

        "threshold_analysis": threshold_results,

        "limitations": [

            "Trained on parameterized configurations "
            "of one demonstration network topology.",

            "LOFO validation evaluates unseen simulated "
            "configurations, not independent real-world feeders.",

            "Target represents simulated VUF threshold "
            "exceedance, not historical PQ incidents.",

            "Random Forest scores are not calibrated probabilities.",

            "Threshold comparison uses the same out-of-fold "
            "predictions and is exploratory.",

            "Independent engineering validation is required."

        ]

    }

    joblib.dump(
        model_bundle,
        MODEL_FILE
    )

    # =====================================
    # COMPLETION
    # =====================================

    print("\n==========================================")
    print(" MODEL SAVED SUCCESSFULLY")
    print("==========================================")

    print(
        "Location:",
        MODEL_FILE
    )

    print(
        "Validation method: LOFO"
    )

    print(
        "Configurations tested:",
        len(unique_groups)
    )

    print(
        "Deployment threshold:",
        BASELINE_THRESHOLD
    )

    print("\nIMPORTANT:")

    print(
        "Deployment model trained using all available "
        "simulated samples."
    )

    print(
        "Evaluation metrics are based on out-of-fold predictions."
    )

    print(
        "Threshold results are exploratory, not independent "
        "final validation."
    )

    print(
        "Model is a research screening prototype, "
        "not an engineering approval system."
    )

    print("\n==========================================")


# =========================================
# PROGRAM ENTRY POINT
# =========================================

if __name__ == "__main__":

    train_model()
