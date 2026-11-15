
import csv
from pathlib import Path


# =========================================
# PROJECT SETTINGS
# =========================================

BASE_DIR = Path(__file__).resolve().parents[1]

RESULT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "integrated_hosting_results.csv"
)

# Existing aggregated solar capacity in master.dss
EXISTING_SOLAR_KW = 200


# =========================================
# LOAD SIMULATION RESULTS
# =========================================

def load_simulation_results():

    if not RESULT_FILE.exists():
        raise FileNotFoundError(
            "Integrated simulation results not found. "
            "Run integrated_hosting_assessment.py first."
        )

    with open(
        RESULT_FILE,
        "r",
        newline="",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)
        results = list(reader)

    if not results:
        raise ValueError("Simulation results are empty.")

    return sorted(
        results,
        key=lambda row: float(row["solar_kw"])
    )


# =========================================
# FIND DEMONSTRATED SOLAR CAPACITY
# =========================================

def find_demonstrated_capacity(results):

    # The sweep must start at zero.
    if float(results[0]["solar_kw"]) != 0:
        raise ValueError(
            "Simulation sweep must include 0 kW."
        )

    last_passing_capacity = None
    first_limiting_factor = "Not identified"

    expected_capacity = 0

    for row in results:

        solar_kw = float(row["solar_kw"])

        # Stop if a simulation level is missing.
        if solar_kw != expected_capacity:
            break

        result = row["result"]

        if result == "PASS":

            last_passing_capacity = solar_kw

            # Current sweep uses 25 kW increments.
            expected_capacity += 25

        else:

            if result == "NON_CONVERGED":
                first_limiting_factor = (
                    "Power flow did not converge"
                )
            else:
                first_limiting_factor = result.replace(
                    "FAIL: ", ""
                )

            break

    return last_passing_capacity, first_limiting_factor


# =========================================
# ASSESS NEW SOLAR CONNECTION
# =========================================

def assess_connection(requested_solar_kw):

    if requested_solar_kw <= 0:
        raise ValueError(
            "Requested solar capacity must be positive."
        )

    results = load_simulation_results()

    demonstrated_capacity, limiting_factor = (
        find_demonstrated_capacity(results)
    )

    if demonstrated_capacity is None:

        return {
            "status": "BASELINE_NOT_ESTABLISHED",
            "message": (
                "The feeder has no demonstrated passing "
                "baseline. A new connection cannot be assessed."
            )
        }

    # Total solar after proposed connection
    proposed_total_solar = (
        EXISTING_SOLAR_KW + requested_solar_kw
    )

    # Determine whether the sweep reached its maximum
    tested_maximum = max(
        float(row["solar_kw"])
        for row in results
    )

    no_violation_observed = (
        limiting_factor == "Not identified"
        and demonstrated_capacity == tested_maximum
    )

    # Calculate demonstrated additional headroom
    demonstrated_headroom = max(
        0,
        demonstrated_capacity - EXISTING_SOLAR_KW
    )

    # Check whether proposed total is inside the tested range
    if proposed_total_solar <= demonstrated_capacity:

        status = "WITHIN_TESTED_RANGE"

        message = (
            "The proposed connection is within the "
            "tested passing solar-capacity range. "
            "This is a preliminary technical screening, "
            "not an approval."
        )

    elif no_violation_observed:

        status = "INSUFFICIENT_EVIDENCE"

        message = (
            "The proposed total solar capacity exceeds "
            "the maximum simulated value. More simulation "
            "is required before assessing this request."
        )

    else:

        status = "LIMIT_EXCEEDED"

        message = (
            "The proposed total solar capacity exceeds "
            "the last demonstrated passing simulation point. "
            "A finer engineering study is required."
        )

    return {
        "status": status,
        "existing_solar_kw": EXISTING_SOLAR_KW,
        "requested_new_solar_kw": requested_solar_kw,
        "proposed_total_solar_kw": proposed_total_solar,
        "last_demonstrated_passing_total_kw": (
            demonstrated_capacity
        ),
        "demonstrated_additional_headroom_kw": (
            demonstrated_headroom
        ),
        "first_limiting_factor": limiting_factor,
        "highest_tested_total_kw": tested_maximum,
        "message": message
    }


# =========================================
# DISPLAY ADVISORY REPORT
# =========================================

def main():

    print("=" * 55)
    print("       SOLAR CONNECTION ADVISORY SYSTEM")
    print("=" * 55)

    print(
        f"\nExisting solar capacity: "
        f"{EXISTING_SOLAR_KW} kW"
    )

    try:

        requested = float(
            input("\nEnter proposed new solar capacity (kW): ")
        )

        report = assess_connection(requested)

        print("\n" + "=" * 55)
        print("             CONNECTION ASSESSMENT")
        print("=" * 55)

        for key, value in report.items():

            print(f"{key}: {value}")

        print("\nASSESSMENT COMPLETED!")

    except (ValueError, FileNotFoundError) as error:

        print("\nASSESSMENT ERROR:", error)


if __name__ == "__main__":
    main()
