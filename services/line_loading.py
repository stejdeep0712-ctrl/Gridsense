
from pathlib import Path
import opendssdirect as dss


BASE_DIR = Path(__file__).resolve().parents[1]

DSS_FILE = BASE_DIR / "data" / "opendss" / "master.dss"

LINE_NAME = "FeederLine"

NORMAL_LIMIT_AMPS = 400

EMERGENCY_LIMIT_AMPS = 500

SOLAR_LEVELS = range(0, 501, 25)


def get_line_current():

    # Activate distribution line
    success = dss.Circuit.SetActiveElement(
        f"Line.{LINE_NAME}"
    )

    if not success:
        raise RuntimeError("Could not activate distribution line!")

    # Get current magnitudes and angles
    current_data = dss.CktElement.CurrentsMagAng()

    # First terminal: three phase conductors
    phase_currents = [
        current_data[0],
        current_data[2],
        current_data[4]
    ]

    maximum_current = max(phase_currents)

    return maximum_current, phase_currents


def run_line_loading_sweep():

    if not DSS_FILE.exists():
        raise FileNotFoundError(DSS_FILE)

    # Load circuit
    dss.Text.Command("Clear")
    dss.Text.Command(f'Compile "{DSS_FILE}"')

    print("=" * 60)
    print("          DISTRIBUTION LINE LOADING")
    print("=" * 60)

    print(f"\nNormal current limit: {NORMAL_LIMIT_AMPS} A")
    print(f"Emergency current limit: {EMERGENCY_LIMIT_AMPS} A")

    print("\nRUNNING SOLAR GENERATION TESTS\n")

    for solar_kw in SOLAR_LEVELS:

        # Change solar generation
        dss.Text.Command(
            f"Edit PVSystem.RooftopPV "
            f"pmpp={solar_kw} "
            f"kVA=600 "
            f"irradiance=1"
        )

        # Solve circuit
        dss.Text.Command("Solve")

        if not dss.Solution.Converged():
            print(
                f"Solar: {solar_kw} kW | "
                "Power flow did not converge"
            )
            continue

        # Measure line current
        maximum_current, phase_currents = get_line_current()

        loading_percent = (
            maximum_current / NORMAL_LIMIT_AMPS
        ) * 100

        if maximum_current <= NORMAL_LIMIT_AMPS:
            status = "PASS"
        else:
            status = "NORMAL_LIMIT_EXCEEDED"

        print(
            f"Solar: {solar_kw:>3} kW | "
            f"Phase currents: "
            f"{phase_currents[0]:.2f}, "
            f"{phase_currents[1]:.2f}, "
            f"{phase_currents[2]:.2f} A | "
            f"Maximum: {maximum_current:.2f} A | "
            f"Loading: {loading_percent:.2f}% | "
            f"{status}"
        )

    print("\nLINE THERMAL CHECK COMPLETED!")


if __name__ == "__main__":
    run_line_loading_sweep()
