
# =========================================
# GRIDSENSE AI ENERGY ADVISOR
# =========================================

def generate_energy_advice(
    weather,
    solar_forecast,
    capacity_kw=10,
    electricity_tariff=8
):

    recommendations = []
    observations = []

    # Validate installation parameters
    if capacity_kw <= 0:
        raise ValueError("Capacity must be positive.")

    if electricity_tariff < 0:
        raise ValueError("Tariff cannot be negative.")

    # Extract weather information
    temperature = weather.get("temperature")
    humidity = weather.get("humidity")
    cloud_cover = weather.get("cloud_cover")
    solar_radiation = weather.get("solar_radiation")

    if cloud_cover is not None:

        if cloud_cover >= 70:
            observations.append(
                "Cloud cover is high and may reduce solar energy availability."
            )

        elif cloud_cover <= 20:
            observations.append(
                "Cloud cover is relatively low, indicating favourable sky conditions."
            )

        else:
            observations.append(
                "Moderate cloud cover is present."
            )

    if solar_radiation is not None:

        if solar_radiation >= 500:
            observations.append(
                "Current solar radiation is relatively strong."
            )

        elif solar_radiation <= 100:
            observations.append(
                "Current solar radiation is low. This can occur during nighttime or low-light conditions."
            )

    if temperature is not None and temperature >= 35:
        observations.append(
            "High ambient temperature may increase PV module operating temperature and reduce efficiency."
        )

    if humidity is not None and humidity >= 80:
        observations.append(
            "High relative humidity is currently observed."
        )

    # Extract solar forecast
    estimated_daily_energy = float(
        solar_forecast.get(
            "estimated_total_energy_kwh", 0
        )
    )

    if estimated_daily_energy <= 0:
        recommendations.append(
            "The forecast indicates little or no estimated solar production. Review the forecast period and weather conditions."
        )

    else:
        recommendations.append(
            f"The {capacity_kw} kW system has an estimated energy production of {estimated_daily_energy:.2f} kWh over the forecast period."
        )

    # Estimated financial value
    estimated_value = (
        estimated_daily_energy * electricity_tariff
    )

    # Compare alternative capacities
    capacity_comparison = []

    for capacity in [5, 10, 25, 50]:

        estimated_energy = (
            estimated_daily_energy
            * capacity / capacity_kw
        )

        capacity_comparison.append({
            "capacity_kw": capacity,
            "estimated_energy_kwh": round(
                estimated_energy, 2
            ),
            "estimated_energy_value_inr": round(
                estimated_energy * electricity_tariff, 2
            )
        })

    recommendations.append(
        "Choose an installation capacity based on actual energy demand, available roof area, budget and grid connection limits."
    )

    recommendations.append(
        "These figures are weather-based estimates and do not represent measured solar generation."
    )

    return {
        "location": "Ludhiana, Punjab, India",
        "advisor_type": "Rule-based energy advisory",
        "installation_capacity_kw": capacity_kw,
        "electricity_tariff_inr_per_kwh": electricity_tariff,
        "estimated_forecast_energy_kwh": round(
            estimated_daily_energy, 2
        ),
        "estimated_energy_value_inr": round(
            estimated_value, 2
        ),
        "weather_observations": observations,
        "recommendations": recommendations,
        "capacity_comparison": capacity_comparison,
        "limitations": [
            "Recommendations are based on configured rules.",
            "Weather forecasts are not actual generation measurements.",
            "Alternative capacity estimates assume linear scaling.",
            "No household consumption profile is included.",
            "Final installation decisions require engineering assessment."
        ]
    }
