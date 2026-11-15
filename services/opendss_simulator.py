
from pathlib import Path
import opendssdirect as dss


# Get backend directory
BASE_DIR = Path(__file__).resolve().parents[1]

# OpenDSS circuit file
DSS_FILE = BASE_DIR / "data" / "opendss" / "master.dss"


def run_simulation():

    print("=" * 50)
    print("          OPENDSS FEEDER SIMULATION")
    print("=" * 50)

    # Check whether DSS file exists
    if not DSS_FILE.exists():
        raise FileNotFoundError(
            f"OpenDSS file not found: {DSS_FILE}"
        )

    # Clear previous circuit
    dss.Text.Command("Clear")

    # Load the electrical circuit
    dss.Text.Command(f'Compile "{DSS_FILE}"')

    # Solve power flow
    dss.Text.Command("Solve")

    # Check convergence
    if not dss.Solution.Converged():
        raise RuntimeError(
            "Power flow did not converge!"
        )

    print("\nPOWER FLOW STATUS")
    print("Power flow converged: True")

    # ------------------------------------------------
    # BUS VOLTAGE MEASUREMENTS
    # ------------------------------------------------

    print("\n" + "=" * 50)
    print("             INDIVIDUAL BUS VOLTAGES")
    print("=" * 50)

    bus_names = dss.Circuit.AllBusNames()

    for bus in bus_names:

        # Activate current bus
        dss.Circuit.SetActiveBus(bus)

        # Get node numbers
        nodes = dss.Bus.Nodes()

        # Get voltage magnitude and angle in per-unit
        voltage_data = dss.Bus.puVmagAngle()

        print(f"\nBus: {bus}")

        for i, node in enumerate(nodes):

            magnitude = voltage_data[2 * i]
            angle = voltage_data[2 * i + 1]

            print(
                f"Node {node}: "
                f"{magnitude:.4f} pu, "
                f"Angle: {angle:.2f} degrees"
            )

    # ------------------------------------------------
    # CIRCUIT LOSSES
    # ------------------------------------------------

    print("\n" + "=" * 50)
    print("                CIRCUIT LOSSES")
    print("=" * 50)

    losses = dss.Circuit.Losses()

    active_losses = losses[0] / 1000
    reactive_losses = losses[1] / 1000

    print(
        f"Active losses: {active_losses:.3f} kW"
    )

    print(
        f"Reactive losses: {reactive_losses:.3f} kvar"
    )

    # ------------------------------------------------
    # GENERATION AND LOAD
    # ------------------------------------------------

    print("\n" + "=" * 50)
    print("             CIRCUIT INFORMATION")
    print("=" * 50)

    print(
        "Total active power (kW):",
        round(dss.Circuit.TotalPower()[0], 3)
    )

    print(
        "Total reactive power (kvar):",
        round(dss.Circuit.TotalPower()[1], 3)
    )

    print(
        "Number of buses:",
        len(bus_names)
    )

    # ------------------------------------------------
    # FINAL STATUS
    # ------------------------------------------------

    print("\n" + "=" * 50)
    print("             SIMULATION SUMMARY")
    print("=" * 50)

    print("Simulation status: SUCCESS")
    print("Power flow converged:", dss.Solution.Converged())

    print("\nSIMULATION COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_simulation()
