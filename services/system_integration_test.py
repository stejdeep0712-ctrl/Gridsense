
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "http://127.0.0.1:8000"

passed = 0
failed = 0


def test_api(name, method, endpoint, payload=None, expected_status=200):
    global passed, failed

    url = BASE_URL + endpoint

    try:
        data = None

        headers = {}

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            url,
            data=data,
            headers=headers,
            method=method
        )

        try:
            with urlopen(request, timeout=15) as response:
                status = response.status
                body = response.read().decode("utf-8")

        except HTTPError as error:
            status = error.code
            body = error.read().decode("utf-8")

        if status != expected_status:
            raise AssertionError(
                f"Expected HTTP {expected_status}, received {status}. "
                f"Response: {body}"
            )

        result = json.loads(body) if body else {}

        print(f"[PASS] {name} - HTTP {status}")
        passed += 1

        return result

    except Exception as error:
        print(f"[FAIL] {name} - {error}")
        failed += 1
        return None


def main():

    print("\n======================================")
    print("       GRIDSENSE SYSTEM TEST")
    print("======================================\n")

    # 1. Backend health
    result = test_api(
        "Backend Health",
        "GET",
        "/health"
    )

    if result is not None and result.get("status") != "healthy":
        print("[FAIL] Health response content")
        global failed
        failed += 1

    # 2. Project information
    test_api(
        "Project Information",
        "GET",
        "/project-info"
    )

    # 3. OpenDSS simulation results
    result = test_api(
        "Hosting Simulation Results",
        "GET",
        "/hosting-results"
    )

    if result is not None:
        if "simulation_results" not in result:
            print("[FAIL] Hosting results response structure")
            failed += 1

    # 4. Engineering connection assessment
    result = test_api(
        "Engineering Connection Assessment",
        "POST",
        "/connection-assessment",
        {
            "feeder_id": "F001",
            "requested_solar_kw": 100
        }
    )

    if result is not None:
        if "assessment" not in result:
            print("[FAIL] Engineering assessment response structure")
            failed += 1

    # 5. AI advisory
    result = test_api(
        "AI Hosting Capacity Advisory",
        "POST",
        "/ai-advisory",
        {
            "feeder_id": "F001",
            "peak_load_kw": 300,
            "line_length_km": 0.2,
            "existing_solar_kw": 200,
            "requested_solar_kw": 100
        }
    )

    if result is not None:
        if "ai_advisory" not in result:
            print("[FAIL] AI advisory response structure")
            failed += 1

    # 6. PQ screening
    result = test_api(
        "PQ Voltage Unbalance Screening",
        "POST",
        "/pq-screening",
        {
            "feeder_id": "F001",
            "line_length_km": 2,
            "phase_a_load_kw": 50,
            "phase_b_load_kw": 10,
            "phase_c_load_kw": 5
        }
    )

    if result is not None:
        required_fields = [
            "screening_status",
            "predicted_class",
            "class_1_model_score_percent",
            "limitations"
        ]

        missing = [
            field for field in required_fields
            if field not in result
        ]

        if missing:
            print(
                "[FAIL] PQ response missing fields:",
                missing
            )
            failed += 1

    # 7. Invalid PQ input should be rejected
    test_api(
        "PQ Input Validation",
        "POST",
        "/pq-screening",
        {
            "feeder_id": "F001",
            "line_length_km": -2,
            "phase_a_load_kw": 50,
            "phase_b_load_kw": 10,
            "phase_c_load_kw": 5
        },
        expected_status=422
    )

    print("\n======================================")
    print("             TEST SUMMARY")
    print("======================================")

    print(f"Passed checks: {passed}")
    print(f"Failed checks: {failed}")

    if failed == 0:
        print("\nALL SYSTEM TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED. CHECK THE ERRORS ABOVE.")

    print("======================================")


if __name__ == "__main__":
    main()
