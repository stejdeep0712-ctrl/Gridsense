
from pathlib import Path

import opendssdirect as dss
import services.pq_simulation as pq

LINE_LENGTHS_KM = [0.2, 0.5, 1.0, 2.0]

LOAD_SCENARIOS = [
    (20, 10, 5),
    (30, 10, 5),
    (40, 10, 5),
    (50, 10, 5),
]

def run_test():

    print("\n========== PQ SENSITIVITY TEST ==========")

    print(
        f"{'Length':<10}"
        f"{'Phase A':<12}"
        f"{'Phase B':<12}"
        f"{'Phase C':<12}"
        f"{'VUF (%)':<12}"
        f"{'Converged':<12}"
    )

    for length in LINE_LENGTHS_KM:

        for phase_a, phase_b, phase_c in LOAD_SCENARIOS:

            try:
                pq.load_feeder()

                # Change feeder line length for this scenario
                dss.Text.Command(
                    f"Edit Line.FeederLine length={length}"
                )

                # Configure phase-specific loads
                pq.PHASE_A_LOAD_KW = phase_a
                pq.PHASE_B_LOAD_KW = phase_b
                pq.PHASE_C_LOAD_KW = phase_c

                pq.add_phase_loads()

                dss.Solution.Solve()

                converged = dss.Solution.Converged()

                if not converged:
                    print(
                        f"{length:<10}"
                        f"{phase_a:<12}"
                        f"{phase_b:<12}"
                        f"{phase_c:<12}"
                        f"{'N/A':<12}"
                        f"{'NO':<12}"
                    )
                    continue

                voltages = pq.get_phase_voltages("EndBus")

                vuf, positive, negative = pq.calculate_vuf(
                    voltages
                )

                print(
                    f"{length:<10}"
                    f"{phase_a:<12}"
                    f"{phase_b:<12}"
                    f"{phase_c:<12}"
                    f"{vuf:<12.4f}"
                    f"{'YES':<12}"
                )

            except Exception as error:
                print(
                    f"ERROR at {length} km, "
                    f"loads {phase_a}/{phase_b}/{phase_c}: "
                    f"{error}"
                )

    print("\n=========================================")
    print("Sensitivity test completed.")
    print("These are simulated engineering scenarios,")
    print("not historical PQ incidents.")


if __name__ == "__main__":
    run_test()
