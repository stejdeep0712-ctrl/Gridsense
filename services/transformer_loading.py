
from pathlib import Path
import math
import opendssdirect as dss


BASE_DIR = Path(__file__).resolve().parents[1]

DSS_FILE = BASE_DIR / "data" / "opendss" / "master.dss"

TRANSFORMER_NAME = "SubXf"

TRANSFORMER_RATING_KVA = 1000

SOLAR_LEVELS = range(0, 501, 25)


def get_transformer_loading():

    # Activate transformer
    success = dss.Circuit.SetActiveElement(
        f"Transformer.{TRANSFORMER_NAME}"
    )

    if not success:
        raise RuntimeError("Could not activate transformer!")

    # Read terminal power values
    powers = dss.CktElement.Powers()

    if len(powers) < 6:
        raise RuntimeError(
            "Transformer phase power measurements unavailable."
        )

    # First three phase conductors at terminal 1
    active_power = sum(powers[i] for i in [0, 2, 4])
    reactive_power = sum(powers[i] for i in [1, 3, 5])

    apparent_power = math.hypot(
        active_power,
        reactive_power
    )

    loading_percent = (
        apparent_power / TRANSFORMER_RATING_KVA
    ) * 100

    return apparent_power, loading_percent


def run_transformer_sweep():

    if not DSS_FILE.exists():
        raise FileNotFoundError(DSS_FILE)

    dss.Text.Command("Clear")
    dss.Text.Command(f'Compile "{DSS_FILE}"')

    print("=" * 55)
    print("       TRANSFORMER LOADING SIMULATION")
    print("=" * 55)

    print(
        f"\nTransformer rating: "
        f"{TRANSFORMER_RATING_KVA} kVA"
    )

    print("\nSOLAR GENERATION TESTS\n")

    for solar_kw in SOLAR_LEVELS:

        dss.Text.Command(
            f"Edit PVSystem.RooftopPV "
            f"pmpp={solar_kw} "
            f"kVA=600 "
            f"irradiance=1"
        )

        dss.Text.Command("Solve")

        if not dss.Solution.Converged():
            print(
                f"{solar_kw} kW | "
                "Power flow did not converge"
            )
            continue

        transformer_kva, loading_percent = (
            get_transformer_loading()
        )

        status = (
            "PASS"
            if loading_percent <= 100
            else "OVERLOADED"
        )

        print(
            f"Solar: {solar_kw:>3} kW | "
            f"Transformer: {transformer_kva:.2f} kVA | "
            f"Loading: {loading_percent:.2f}% | "
            f"{status}"
        )

    print("\nTRANSFORMER CHECK COMPLETED!")


if __name__ == "__main__":
    run_transformer_sweep()

