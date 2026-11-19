from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
from socket import timeout as SocketTimeout
import os
from google import genai
from google.genai import types
import csv
import json
import time
import joblib
import numpy as np

from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db import get_db, Base, engine
from database.models import Feeder, AssessmentHistory

from ml.advisory_predictor import generate_ai_advisory
from services.connection_advisor import assess_connection
from services.energy_advisor import generate_energy_advice


# =========================================
# PATH CONFIGURATION
# =========================================

BASE_DIR = Path(__file__).resolve().parent

FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data" / "processed"
MODEL_DIR = BASE_DIR / "models" / "saved"

PQ_MODEL_FILE = MODEL_DIR / "pq_screening_model.joblib"


# =========================================
# FASTAPI APPLICATION
# =========================================

app = FastAPI(
    title="GridSense - Renewable Energy Advisor",
    description=(
        "AI-powered renewable energy hosting capacity "
        "and power quality advisory system"
    ),
    version="1.3.0"
)


# Initialize database tables
Base.metadata.create_all(bind=engine)


# =========================================
# CORS CONFIGURATION
# =========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://magenta-raindrop-72a060.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================
# WEATHER CACHE
# =========================================

LIVE_WEATHER_CACHE = {
    "data": None,
    "timestamp": 0
}

SOLAR_FORECAST_CACHE = {}

WEATHER_CACHE_SECONDS = 600
FORECAST_CACHE_SECONDS = 1800


# =========================================
# COMMON WEATHER REQUEST FUNCTION
# =========================================

def fetch_weather_data(url: str, timeout: int = 20):

    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=f"Weather service error: HTTP {error.code}"
        )

    except (URLError, TimeoutError, SocketTimeout, OSError) as error:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to the weather service."
        )

    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=502,
            detail="Invalid response from the weather service."
        )


# =========================================
# LIVE WEATHER AND SOLAR DATA
# =========================================

@app.get("/live-data")
def get_live_data():

    # Return cached data if it is still fresh
    if (
        LIVE_WEATHER_CACHE["data"] is not None
        and time.time() - LIVE_WEATHER_CACHE["timestamp"]
        < WEATHER_CACHE_SECONDS
    ):
        return LIVE_WEATHER_CACHE["data"]

    latitude = 30.9010
    longitude = 75.8573

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "cloud_cover,"
            "wind_speed_10m,"
            "shortwave_radiation"
        ),
        "timezone": "Asia/Kolkata"
    }

    url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urlencode(params)
    )

    data = fetch_weather_data(url)

    current = data.get("current", {})
    units = data.get("current_units", {})

    if not current:
        raise HTTPException(
            status_code=502,
            detail="Live weather data is unavailable."
        )

    result = {
        "source": "Open-Meteo",
        "location": "Ludhiana, Punjab, India",
        "coordinates": {
            "latitude": latitude,
            "longitude": longitude
        },
        "timestamp": current.get("time"),
        "weather": {
            "temperature": current.get("temperature_2m"),
            "temperature_unit": units.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "humidity_unit": units.get("relative_humidity_2m"),
            "feels_like": current.get("apparent_temperature"),
            "precipitation": current.get("precipitation"),
            "cloud_cover": current.get("cloud_cover"),
            "wind_speed": current.get("wind_speed_10m"),
            "solar_radiation": current.get("shortwave_radiation"),
            "solar_radiation_unit": units.get(
                "shortwave_radiation"
            )
        }
    }

    LIVE_WEATHER_CACHE["data"] = result
    LIVE_WEATHER_CACHE["timestamp"] = time.time()

    return result


# =========================================
# 24-HOUR SOLAR GENERATION FORECAST
# =========================================

@app.get("/solar-forecast")
def get_solar_forecast(capacity_kw: float = 10.0):

    if not 0 < capacity_kw <= 1000:
        raise HTTPException(
            status_code=400,
            detail="Solar capacity must be between 0 and 1000 kW."
        )

    cache_key = round(capacity_kw, 2)

    # Return cached forecast
    cached = SOLAR_FORECAST_CACHE.get(cache_key)

    if (
        cached
        and time.time() - cached["timestamp"]
        < FORECAST_CACHE_SECONDS
    ):
        return cached["data"]

    latitude = 30.9010
    longitude = 75.8573

    performance_ratio = 0.80

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": (
            "shortwave_radiation,"
            "temperature_2m,"
            "cloud_cover"
        ),
        "forecast_hours": 24,
        "timezone": "Asia/Kolkata"
    }

    url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urlencode(params)
    )

    data = fetch_weather_data(url, timeout=25)

    hourly = data.get("hourly", {})

    times = hourly.get("time", [])
    radiation = hourly.get("shortwave_radiation", [])
    temperatures = hourly.get("temperature_2m", [])
    clouds = hourly.get("cloud_cover", [])

    if not times or len(times) != 24:
        raise HTTPException(
            status_code=502,
            detail="Incomplete 24-hour forecast received."
        )

    forecasts = []
    total_energy = 0.0

    for i in range(len(times)):

        irradiance = radiation[i]

        if irradiance is None:
            raise HTTPException(
                status_code=502,
                detail="Missing solar radiation forecast."
            )

        irradiance = max(0.0, float(irradiance))

        hourly_energy = (
            capacity_kw
            * (irradiance / 1000.0)
            * performance_ratio
        )

        total_energy += hourly_energy

        forecasts.append({
            "time": times[i],
            "solar_radiation_w_m2": irradiance,
            "temperature_c": temperatures[i],
            "cloud_cover_percent": clouds[i],
            "estimated_generation_kwh": round(
                hourly_energy, 3
            )
        })

    result = {
        "location": "Ludhiana, Punjab, India",
        "capacity_kw": capacity_kw,
        "performance_ratio": performance_ratio,
        "forecast_period_hours": len(forecasts),
        "estimated_total_energy_kwh": round(
            total_energy, 2
        ),
        "forecast": forecasts,
        "method": "Weather-based PV generation estimate",
        "limitations": [
            "Uses horizontal shortwave radiation as a solar-resource proxy.",
            "Panel tilt, orientation and shading are not modelled.",
            "Performance ratio is an assumed value.",
            "Forecast is not actual measured solar generation."
        ]
    }

    SOLAR_FORECAST_CACHE[cache_key] = {
        "data": result,
        "timestamp": time.time()
    }

    return result


# =========================================
# HISTORICAL SOLAR PERFORMANCE ANALYTICS
# =========================================

@app.get("/solar-analytics")
def get_solar_analytics(
    year: int = 2025,
    capacity_kw: float = 10.0
):

    if year < 2000 or year > 2025:
        raise HTTPException(
            status_code=400,
            detail="Choose a complete year between 2000 and 2025."
        )

    if not 0 < capacity_kw <= 1000:
        raise HTTPException(
            status_code=400,
            detail="Capacity must be between 0 and 1000 kW."
        )

    latitude = 30.9010
    longitude = 75.8573
    performance_ratio = 0.80

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "daily": "shortwave_radiation_sum",
        "timezone": "Asia/Kolkata"
    }

    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        + urlencode(params)
    )

    data = fetch_weather_data(url, timeout=30)

    daily = data.get("daily", {})

    dates = daily.get("time", [])
    radiation_values = daily.get(
        "shortwave_radiation_sum", []
    )

    if not dates or len(dates) != len(radiation_values):
        raise HTTPException(
            status_code=502,
            detail="Historical solar data is incomplete."
        )

    monthly_energy = {
        month: 0.0 for month in range(1, 13)
    }

    monthly_days = {
        month: 0 for month in range(1, 13)
    }

    total_energy = 0.0

    for date, radiation in zip(dates, radiation_values):

        if radiation is None:
            continue

        month = int(date[5:7])
        radiation_mj = max(0.0, float(radiation))

        daily_energy = (
            capacity_kw
            * (radiation_mj / 3.6)
            * performance_ratio
        )

        monthly_energy[month] += daily_energy
        monthly_days[month] += 1
        total_energy += daily_energy

    month_names = [
        "January", "February", "March",
        "April", "May", "June",
        "July", "August", "September",
        "October", "November", "December"
    ]

    monthly_results = []

    for month in range(1, 13):

        energy = monthly_energy[month]
        days = monthly_days[month]

        monthly_results.append({
            "month": month_names[month - 1],
            "estimated_energy_kwh": round(energy, 2),
            "average_daily_energy_kwh": round(
                energy / days, 2
            ) if days else 0,
            "days_available": days
        })

    return {
        "location": "Ludhiana, Punjab, India",
        "historical_year": year,
        "capacity_kw": capacity_kw,
        "performance_ratio": performance_ratio,
        "estimated_annual_energy_kwh": round(
            total_energy, 2
        ),
        "monthly_analytics": monthly_results,
        "data_source": "Open-Meteo Historical Weather API",
        "method": "Historical radiation-based PV estimate",
        "limitations": [
            "Uses historical horizontal solar radiation.",
            "Panel tilt, orientation and shading are not modelled.",
            "Performance ratio is an assumed value.",
            "This is estimated energy, not actual meter data.",
            "Historical weather does not guarantee future generation."
        ]
    }


# =========================================
# ENERGY ADVISOR REQUEST
# =========================================

class EnergyAdvisorRequest(BaseModel):

    capacity_kw: float = Field(
        default=10,
        gt=0,
        le=1000
    )

    electricity_tariff: float = Field(
        default=8,
        ge=0,
        le=100
    )


# =========================================
# ENERGY ADVISOR API
# =========================================

@app.post("/energy-advisor")
def energy_advisor(request: EnergyAdvisorRequest):

    try:

        weather_response = get_live_data()

        forecast_response = get_solar_forecast(
            capacity_kw=request.capacity_kw
        )

        result = generate_energy_advice(
            weather=weather_response.get("weather", {}),
            solar_forecast=forecast_response,
            capacity_kw=request.capacity_kw,
            electricity_tariff=request.electricity_tariff
        )

        return result

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Energy advisory failed: " + str(error)
        )


# =========================================
# HOME
# =========================================

@app.get("/")
def home():

    return {
        "message": "GridSense Backend",
        "status": "Running",
        "version": "1.3.0"
    }


# =========================================
# HEALTH CHECK
# =========================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "backend": "operational"
    }


# =========================================
# PROJECT INFORMATION
# =========================================

@app.get("/project-info")
def project_info():

    return {
        "project": (
            "Renewable Energy Hosting Capacity "
            "and Power Quality Advisory System"
        ),
        "models": [
            "Hosting Capacity Regression",
            "Engineering Constraint Classification",
            "Multi-configuration Simulated PQ Classification"
        ]
    }


# =========================================
# SOLAR CONNECTION REQUEST
# =========================================

class SolarConnectionRequest(BaseModel):

    feeder_id: str = Field(
        default="F001",
        min_length=1
    )

    requested_solar_kw: float = Field(
        gt=0,
        le=10000
    )


# =========================================
# HISTORY SAVING HELPER
# =========================================

def save_history_record(
    db: Session,
    feeder_code: str,
    assessment_type: str,
    status: str,
    input_data: dict,
    result_data: dict
):

    try:

        feeder = db.query(Feeder).filter(
            Feeder.feeder_id == feeder_code
        ).first()

        record = AssessmentHistory(
            feeder_id=feeder.id if feeder else None,
            feeder_code=feeder_code,
            assessment_type=assessment_type,
            status=status,
            input_data=json.dumps(input_data),
            result_data=json.dumps(result_data)
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record.id

    except Exception:
        db.rollback()
        raise


# =========================================
# SOLAR CONNECTION ASSESSMENT
# =========================================

@app.post("/connection-assessment")
def connection_assessment(
    request: SolarConnectionRequest,
    db: Session = Depends(get_db)
):

    try:

        result = assess_connection(
            request.requested_solar_kw
        )

        result_status = (
            str(result.get("status", "COMPLETED"))
            if isinstance(result, dict)
            else "COMPLETED"
        )

        save_history_record(
            db=db,
            feeder_code=request.feeder_id,
            assessment_type="ENGINEERING_CONNECTION",
            status=result_status,
            input_data={
                "requested_solar_kw": request.requested_solar_kw
            },
            result_data=result
        )

        return {
            "feeder_id": request.feeder_id,
            "assessment": result
        }

    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Assessment failed: " + str(error)
        )


# =========================================
# OPENDSS HOSTING RESULTS
# =========================================

@app.get("/hosting-results")
def get_hosting_results():

    results_file = (
        DATA_DIR / "integrated_hosting_results.csv"
    )

    if not results_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Run the integrated hosting assessment first."
        )

    with open(
        results_file,
        "r",
        newline="",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)
        results = list(reader)

    return {
        "total_records": len(results),
        "simulation_results": results
    }


# =========================================
# AI ADVISORY REQUEST
# =========================================

class AIAdvisoryRequest(BaseModel):

    feeder_id: str = Field(
        default="F001",
        min_length=1
    )

    peak_load_kw: float = Field(gt=0)

    line_length_km: float = Field(gt=0)

    existing_solar_kw: float = Field(ge=0)

    requested_solar_kw: float = Field(gt=0)


# =========================================
# AI HOSTING CAPACITY ADVISORY
# =========================================

@app.post("/ai-advisory")
def ai_advisory(
    request: AIAdvisoryRequest,
    db: Session = Depends(get_db)
):

    try:

        result = generate_ai_advisory(
            peak_load_kw=request.peak_load_kw,
            line_length_km=request.line_length_km,
            existing_solar_kw=request.existing_solar_kw,
            requested_solar_kw=request.requested_solar_kw
        )

        result_status = (
            str(result.get("status", "COMPLETED"))
            if isinstance(result, dict)
            else "COMPLETED"
        )

        save_history_record(
            db=db,
            feeder_code=request.feeder_id,
            assessment_type="AI_ADVISORY",
            status=result_status,
            input_data={
                "peak_load_kw": request.peak_load_kw,
                "line_length_km": request.line_length_km,
                "existing_solar_kw": request.existing_solar_kw,
                "requested_solar_kw": request.requested_solar_kw
            },
            result_data=result
        )

        return {
            "feeder_id": request.feeder_id,
            "ai_advisory": result
        }

    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="AI advisory failed: " + str(error)
        )


# =========================================
# LOAD PQ MODEL
# =========================================

def load_pq_model():

    if not PQ_MODEL_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "PQ screening model not found. "
                "Train the model first."
            )
        )

    try:

        bundle = joblib.load(PQ_MODEL_FILE)

        required_keys = ["model", "features"]

        for key in required_keys:
            if key not in bundle:
                raise ValueError(
                    f"PQ model bundle missing: {key}"
                )

        return bundle

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Unable to load PQ model: " + str(error)
        )


# =========================================
# PQ MODEL INFORMATION
# =========================================

@app.get("/pq-model-info")
def pq_model_info():

    bundle = load_pq_model()

    return {
        "model_type": (
            "Simulated VUF threshold-exceedance classifier"
        ),
        "features": bundle.get("features", []),
        "screening_threshold_percent": bundle.get(
            "screening_threshold_percent", 2.0
        ),
        "decision_threshold": bundle.get(
            "decision_threshold", 0.5
        ),
        "validation_method": bundle.get("validation_method"),
        "evaluation": bundle.get("evaluation", {}),
        "fold_results": bundle.get("fold_results", []),
        "threshold_analysis": bundle.get(
            "threshold_analysis", []
        ),
        "limitations": bundle.get("limitations", [])
    }


# =========================================
# PQ SCREENING REQUEST
# =========================================

class PQScreeningRequest(BaseModel):

    feeder_id: str = Field(
        default="FDR_SHORT",
        min_length=1
    )

    line_length_km: float = Field(gt=0, le=100)
    line_r1: float = Field(gt=0, le=100)
    line_x1: float = Field(gt=0, le=100)

    phase_a_load_kw: float = Field(ge=0, le=10000)
    phase_b_load_kw: float = Field(ge=0, le=10000)
    phase_c_load_kw: float = Field(ge=0, le=10000)


# =========================================
# ASSESSMENT HISTORY REQUEST
# =========================================

class AssessmentHistoryRequest(BaseModel):

    feeder_code: str = Field(
        min_length=1,
        max_length=100
    )

    assessment_type: str = Field(
        min_length=1,
        max_length=50
    )

    status: str = Field(
        min_length=1,
        max_length=100
    )

    input_data: dict
    result_data: dict


# =========================================
# MULTI-CONFIGURATION PQ SCREENING
# =========================================

@app.post("/pq-screening")
def pq_screening(
    request: PQScreeningRequest,
    db: Session = Depends(get_db)
):

    try:

        model_bundle = load_pq_model()

        model = model_bundle["model"]
        features = model_bundle["features"]

        decision_threshold = float(
            model_bundle.get("decision_threshold", 0.5)
        )

        if not 0 < decision_threshold < 1:
            raise ValueError(
                "Invalid saved decision threshold."
            )

        input_values = {
            "line_length_km": request.line_length_km,
            "line_r1": request.line_r1,
            "line_x1": request.line_x1,
            "phase_a_load_kw": request.phase_a_load_kw,
            "phase_b_load_kw": request.phase_b_load_kw,
            "phase_c_load_kw": request.phase_c_load_kw
        }

        missing_features = [
            feature for feature in features
            if feature not in input_values
        ]

        if missing_features:
            raise ValueError(
                f"Missing model features: {missing_features}"
            )

        input_data = np.array(
            [[input_values[feature] for feature in features]],
            dtype=float
        )

        if not np.isfinite(input_data).all():
            raise ValueError("Invalid numerical input.")

        if 1 not in list(model.classes_):
            raise ValueError(
                "PQ model does not contain class 1."
            )

        class_1_index = list(model.classes_).index(1)

        probabilities = model.predict_proba(input_data)[0]

        class_1_score = float(
            probabilities[class_1_index]
        )

        predicted_class = int(
            class_1_score >= decision_threshold
        )

        if predicted_class == 1:

            status = "VUF_LIMIT_EXCEEDANCE_SCREENED"
            class_label = "VUF limit exceeded"

            message = (
                "The model flags this scenario as a possible "
                "simulated VUF screening-limit exceedance. "
                "Further engineering analysis is required."
            )

        else:

            status = "WITHIN_SIMULATED_VUF_LIMIT"
            class_label = "Within VUF limit"

            message = (
                "The model predicts this scenario is within "
                "the configured simulated VUF screening limit. "
                "This is not an engineering approval."
            )

        response = {
            "feeder_id": request.feeder_id,
            "screening_status": status,
            "predicted_class": predicted_class,
            "class_label": class_label,
            "class_1_model_score_percent": round(
                class_1_score * 100, 2
            ),
            "decision_threshold": decision_threshold,
            "input_parameters": input_values,
            "screening_threshold_percent": model_bundle.get(
                "screening_threshold_percent", 2.0
            ),
            "message": message,
            "model_type": (
                "Multi-configuration simulated "
                "VUF threshold-exceedance classifier"
            ),
            "validation_method": model_bundle.get(
                "validation_method"
            ),
            "evaluation": model_bundle.get("evaluation", {}),
            "limitations": model_bundle.get(
                "limitations",
                [
                    "Model trained on simulated configurations "
                    "of one demonstration network topology.",
                    "Not validated on independently sourced "
                    "real-world feeders.",
                    "Not trained on historical PQ incidents.",
                    "Model scores are not calibrated real-world "
                    "probabilities.",
                    "Physical power-quality measurements and "
                    "engineer review are required."
                ]
            )
        }

        save_history_record(
            db=db,
            feeder_code=request.feeder_id,
            assessment_type="PQ_SCREENING",
            status=status,
            input_data=input_values,
            result_data=response
        )

        return response

    except HTTPException:
        raise

    except (
        ValueError,
        KeyError,
        FileNotFoundError
    ) as error:

        raise HTTPException(
            status_code=400,
            detail="PQ screening error: " + str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail="PQ screening failed: " + str(error)
        )


# =========================================
# ASSESSMENT HISTORY API
# =========================================

@app.post("/assessment-history")
def save_assessment_history(
    request: AssessmentHistoryRequest,
    db: Session = Depends(get_db)
):

    try:

        feeder = db.query(Feeder).filter(
            Feeder.feeder_id == request.feeder_code
        ).first()

        record = AssessmentHistory(
            feeder_id=feeder.id if feeder else None,
            feeder_code=request.feeder_code,
            assessment_type=request.assessment_type,
            status=request.status,
            input_data=json.dumps(request.input_data),
            result_data=json.dumps(request.result_data)
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return {
            "message": "Assessment saved successfully",
            "assessment_id": record.id,
            "feeder_code": record.feeder_code,
            "assessment_type": record.assessment_type,
            "status": record.status,
            "created_at": record.created_at
        }

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Could not save assessment history."
        )


@app.get("/assessment-history")
def get_assessment_history(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):

    if skip < 0 or limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=400,
            detail=(
                "Pagination values must use skip >= 0 "
                "and limit between 1 and 1000."
            )
        )

    records = (
        db.query(AssessmentHistory)
        .order_by(AssessmentHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total_records": db.query(
            AssessmentHistory
        ).count(),

        "assessments": [
            {
                "id": record.id,
                "feeder_code": record.feeder_code,
                "assessment_type": record.assessment_type,
                "status": record.status,
                "input_data": json.loads(record.input_data),
                "result_data": json.loads(record.result_data),
                "created_at": record.created_at
            }
            for record in records
        ]
    }


@app.get("/assessment-history/{assessment_id}")
def get_assessment_by_id(
    assessment_id: int,
    db: Session = Depends(get_db)
):

    record = db.query(AssessmentHistory).filter(
        AssessmentHistory.id == assessment_id
    ).first()

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Assessment record not found."
        )

    return {
        "id": record.id,
        "feeder_code": record.feeder_code,
        "assessment_type": record.assessment_type,
        "status": record.status,
        "input_data": json.loads(record.input_data),
        "result_data": json.loads(record.result_data),
        "created_at": record.created_at
    }


# =========================================
# FRONTEND DASHBOARD
# =========================================

if FRONTEND_DIR.exists():

    app.mount(
        "/dashboard",
        StaticFiles(
            directory=FRONTEND_DIR,
            html=True
        ),
        name="dashboard"
    )
    

# =========================================
# GRIDSENSE AI CHATBOT
# =========================================

class ChatMessage(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)


@app.post("/chat")
def gridsense_chat(request: ChatRequest):

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured."
        )

    try:
        client = genai.Client(api_key=api_key)

        system_instruction = """
        You are GridSense AI, an assistant for a renewable energy
        hosting capacity and power quality advisory platform.

        Help users understand:
        - Renewable energy and solar PV systems
        - Distribution network hosting capacity
        - Voltage regulation and power quality
        - Voltage unbalance factor (VUF)
        - Electrical engineering assessments
        - Solar generation and energy analysis

        Give clear, professional and technically useful answers.

        Never invent GridSense assessment results, measurements,
        or live dashboard values. If data is not provided, say so.

        Your advice is informational and does not replace
        professional engineering verification or safety procedures.
        """

        contents = []

        for item in request.history:
            if item.role not in ("user", "model"):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid chat history role."
                )

            contents.append(
                types.Content(
                    role=item.role,
                    parts=[
                        types.Part.from_text(text=item.content)
                    ]
                )
            )

        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=request.message)
                ]
            )
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.5,
                max_output_tokens=1000
            )
        )

        answer = response.text

        if not answer:
            raise ValueError("Empty AI response")

        return {
            "reply": answer,
            "assistant": "GridSense AI"
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="AI assistant could not generate a response."
        )
