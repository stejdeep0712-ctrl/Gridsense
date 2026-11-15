
from pathlib import Path
import joblib


BASE_DIR = Path(__file__).resolve().parents[1]

MODEL_DIR = BASE_DIR / "models" / "saved"


def explain_model(model_file, model_name):

    path = MODEL_DIR / model_file

    if not path.exists():
        raise FileNotFoundError(path)

    bundle = joblib.load(path)

    model = bundle["model"]
    features = bundle["features"]

    importances = model.feature_importances_

    results = sorted(
        zip(features, importances),
        key=lambda item: item[1],
        reverse=True
    )

    print("\n" + "=" * 55)
    print(model_name)
    print("=" * 55)

    for feature, importance in results:

        percentage = importance * 100

        bar = "█" * int(percentage / 2)

        print(
            f"{feature:30} "
            f"{percentage:6.2f}% {bar}"
        )

    print("\nInterpretation:")

    if results:

        top_feature = results[0][0]

        print(
            f"The most influential feature according "
            f"to this model is: {top_feature}"
        )

    print(
        "\nNote: Feature importance indicates model "
        "dependence, not causation."
    )


if __name__ == "__main__":

    explain_model(
        "hosting_capacity_model.joblib",
        "HOSTING CAPACITY REGRESSION"
    )

    explain_model(
        "constraint_risk_model.joblib",
        "ENGINEERING CONSTRAINT CLASSIFICATION"
    )
