
const API_BASE = "https://gridsense-4il3.onrender.com";

const API = {
    solarAnalytics: `${API_BASE}/solar-analytics`,
    health: `${API_BASE}/health`,
    connection: `${API_BASE}/connection-assessment`,
    ai: `${API_BASE}/ai-advisory`,
    pq: `${API_BASE}/pq-screening`,
    pqInfo: `${API_BASE}/pq-model-info`,
    hosting: `${API_BASE}/hosting-results`,
    liveData: `${API_BASE}/live-data`,
    solarForecast: `${API_BASE}/solar-forecast`,
    energyAdvisor: `${API_BASE}/energy-advisor`,
    chat: `${API_BASE}/chat`
};

// =============================================
// HELPER FUNCTIONS
// =============================================

function getValue(id) {
    const element = document.getElementById(id);
    return element ? element.value.trim() : "";
}

function showNumber(value, digits = 2) {
    const number = Number(value);

    return Number.isFinite(number)
        ? number.toFixed(digits)
        : "Unavailable";
}

async function postJSON(url, payload) {
    try {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const text = await response.text();
        let data;

        try {
            data = text ? JSON.parse(text) : {};
        } catch {
            throw new Error("Backend returned an invalid response.");
        }

        if (!response.ok) {
            const detail = data.detail || data.message;

            throw new Error(
                typeof detail === "string"
                    ? detail
                    : JSON.stringify(detail || data)
            );
        }

        return data;

    } catch (error) {
        console.error("API request failed:", error);
        throw error;
    }
}

function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value ?? "Unavailable";
    }
}

function fillList(id, items) {
    const list = document.getElementById(id);

    if (!list) return;

    list.replaceChildren();

    (Array.isArray(items) ? items : []).forEach(item => {
        const li = document.createElement("li");
        li.textContent = String(item);
        list.appendChild(li);
    });
}

// =============================================
// GRIDSENSE SYSTEM STATUS MONITORING
// =============================================

async function checkModuleStatus(endpoint, elementId) {
    const element = document.getElementById(elementId);

    if (!element) return;

    element.textContent = "CHECKING";

    try {
        const response = await fetch(endpoint);

        if (response.status === 404 && endpoint === API.hosting) {
            element.textContent = "NO DATA";
            return;
        }

        if (!response.ok) {
            throw new Error(`Service unavailable (${response.status})`);
        }

        element.textContent = "ACTIVE";

    } catch (error) {
        element.textContent = "OFFLINE";
    }
}

// =============================================
// BACKEND CONNECTION STATUS
// =============================================

async function checkBackend() {
    const status = document.getElementById("connectionStatus");
    const backendStatus = document.getElementById("backendModuleStatus");

    try {
        const response = await fetch(API.health);

        if (!response.ok) {
            throw new Error("Backend unavailable");
        }

        if (status) status.textContent = "Connected";
        if (backendStatus) backendStatus.textContent = "ONLINE";

    } catch (error) {
        if (status) status.textContent = "Disconnected";
        if (backendStatus) backendStatus.textContent = "OFFLINE";
    }
}

// =============================================
// MODULE AVAILABILITY CHECKS
// =============================================

async function loadSystemMonitoring() {
    await Promise.all([
        checkModuleStatus(API.hosting, "engineeringStatus"),
        checkModuleStatus(API.health, "aiModuleStatus"),
        checkModuleStatus(API.pqInfo, "pqModuleStatus")
    ]);
}

// =============================================
// ENGINEERING CONNECTION ASSESSMENT
// =============================================

const engineeringForm = document.getElementById("engineeringForm");

if (engineeringForm) {
    engineeringForm.addEventListener("submit", async event => {
        event.preventDefault();

        const button = engineeringForm.querySelector('button[type="submit"]');
        const error = document.getElementById("engineeringError");

        if (!button || !error) return;

        error.textContent = "";

        const feederId = getValue("engineeringFeeder");
        const requestedSolar = Number(getValue("requestedSolar"));

        if (!feederId || !Number.isFinite(requestedSolar) || requestedSolar <= 0) {
            error.textContent = "Enter a valid feeder ID and solar capacity.";
            return;
        }

        button.disabled = true;
        button.textContent = "Assessing...";

        try {
            const data = await postJSON(API.connection, {
                feeder_id: feederId,
                requested_solar_kw: requestedSolar
            });

            displayEngineeringResults(data);

        } catch (err) {
            error.textContent = err.message;

        } finally {
            button.disabled = false;
            button.textContent = "Assess Solar Connection";
        }
    });
}

// =============================================
// DISPLAY ENGINEERING RESULTS
// =============================================

function displayEngineeringResults(data) {
    const result = data.assessment || {};

    const resultElement = document.getElementById("engineeringResult");
    if (resultElement) {
        resultElement.classList.remove("hidden");
    }

    setText("engineeringStatus",
        (result.status || "Unavailable").replaceAll("_", " "));

    setText("engineeringMessage", result.message);
    setText("existingSolar", `${showNumber(result.existing_solar_kw)} kW`);
    setText("newSolar", `${showNumber(result.requested_new_solar_kw)} kW`);
    setText("totalSolar", `${showNumber(result.proposed_total_solar_kw)} kW`);
    setText("headroom", `${showNumber(result.demonstrated_additional_headroom_kw)} kW`);
    setText("limitingFactor", result.first_limiting_factor);

    if (resultElement) {
        resultElement.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }
}

// =============================================
// AI HOSTING CAPACITY ADVISORY
// =============================================

const aiForm = document.getElementById("aiForm");

if (aiForm) {
    aiForm.addEventListener("submit", async event => {
        event.preventDefault();

        const button = aiForm.querySelector('button[type="submit"]');
        const error = document.getElementById("aiError");

        if (!button || !error) return;

        error.textContent = "";

        const payload = {
            feeder_id: getValue("aiFeeder"),
            peak_load_kw: Number(getValue("peakLoad")),
            line_length_km: Number(getValue("aiLineLength")),
            existing_solar_kw: Number(getValue("existingSolarInput")),
            requested_solar_kw: Number(getValue("aiRequestedSolar"))
        };

        if (
            !payload.feeder_id ||
            !Number.isFinite(payload.peak_load_kw) ||
            payload.peak_load_kw <= 0 ||
            !Number.isFinite(payload.line_length_km) ||
            payload.line_length_km <= 0 ||
            !Number.isFinite(payload.existing_solar_kw) ||
            payload.existing_solar_kw < 0 ||
            !Number.isFinite(payload.requested_solar_kw) ||
            payload.requested_solar_kw <= 0
        ) {
            error.textContent = "Please enter valid feeder and solar details.";
            return;
        }

        button.disabled = true;
        button.textContent = "Running AI models...";

        try {
            const data = await postJSON(API.ai, payload);
            displayAIResults(data.ai_advisory || {});

        } catch (err) {
            error.textContent = err.message;

        } finally {
            button.disabled = false;
            button.textContent = "Generate AI Advisory";
        }
    });
}

// =============================================
// DISPLAY AI RESULTS
// =============================================

function displayAIResults(result) {
    const resultElement = document.getElementById("aiResult");

    if (resultElement) resultElement.classList.remove("hidden");

    setText("aiStatus",
        (result.status || "Unavailable").replaceAll("_", " "));

    setText("aiMessage",
        result.explanation || "No explanation returned.");

    const regression = result.regression_prediction || {};
    const classification = result.classification_prediction || {};
    const inputs = result.inputs || {};

    setText("predictedCapacity",
        `${showNumber(regression.estimated_additional_hosting_capacity_kw)} kW`);

    setText("constraintClass",
        `Class ${classification.predicted_class ?? "Unavailable"}`);

    const class1Score =
        classification.configured_violation_model_score_percent ??
        classification.configured_violation_probability_percent;

    setText("constraintScore",
        class1Score !== undefined && class1Score !== null
            ? `${showNumber(class1Score)}%`
            : "Unavailable");

    setText("aiTotalSolar",
        `${showNumber(inputs.proposed_total_solar_kw)} kW`);

    fillList("aiLimitations", result.limitations);

    if (resultElement) {
        resultElement.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }
}

// =============================================
// PQ FEEDER CONFIGURATION PRESETS
// =============================================

const pqPresets = {
    FDR_SHORT: { length: 0.2, r1: 0.05, x1: 0.04 },
    FDR_MEDIUM: { length: 0.5, r1: 0.05, x1: 0.04 },
    FDR_LONG: { length: 1.0, r1: 0.05, x1: 0.04 },
    FDR_HIGH_IMPEDANCE: { length: 2.0, r1: 0.10, x1: 0.08 }
};

const pqFeeder = document.getElementById("pqFeeder");

if (pqFeeder) {
    pqFeeder.addEventListener("change", () => {
        const preset = pqPresets[pqFeeder.value];

        if (!preset) return;

        document.getElementById("pqLineLength").value = preset.length;
        document.getElementById("pqR1").value = preset.r1;
        document.getElementById("pqX1").value = preset.x1;
    });
}

// =============================================
// CREATE PQ METRIC CARD
// =============================================

function makeMetricCard(label, value) {
    const card = document.createElement("div");
    card.className = "result-item";

    const heading = document.createElement("p");
    heading.textContent = label;

    const valueElement = document.createElement("h3");
    valueElement.textContent = value;

    card.append(heading, valueElement);

    return card;
}

// =============================================
// LOAD SAVED PQ MODEL EVALUATION
// =============================================

async function loadPQModelInfo() {
    const loading = document.getElementById("pqModelLoading");
    const cards = document.getElementById("pqMetricCards");
    const feederContainer = document.getElementById("pqFeederValidation");
    const thresholdContainer = document.getElementById("pqThresholdAnalysis");

    if (!loading || !cards) return;

    try {
        const response = await fetch(API.pqInfo);
        const info = await response.json();

        if (!response.ok) {
            throw new Error(
                typeof info.detail === "string"
                    ? info.detail
                    : "Could not load PQ model information."
            );
        }

        const evaluation = info.evaluation || {};

        cards.replaceChildren(
            makeMetricCard("LOFO Accuracy",
                `${showNumber(evaluation.accuracy * 100)}%`),
            makeMetricCard("Balanced Accuracy",
                `${showNumber(evaluation.balanced_accuracy * 100)}%`),
            makeMetricCard("Class 1 Precision",
                `${showNumber(evaluation.class_1_precision * 100)}%`),
            makeMetricCard("Class 1 Recall",
                `${showNumber(evaluation.class_1_recall * 100)}%`),
            makeMetricCard("Class 1 F1",
                `${showNumber(evaluation.class_1_f1 * 100)}%`),
            makeMetricCard("Decision Threshold",
                showNumber(info.decision_threshold))
        );

        loading.textContent =
            `Validation: ${info.validation_method || "Not reported"}. ` +
            "These are out-of-fold metrics on simulated configurations.";

        if (feederContainer) {
            feederContainer.replaceChildren();

            const heading = document.createElement("h3");
            heading.textContent = "Feeder-wise validation";
            feederContainer.appendChild(heading);

            const folds = Array.isArray(info.fold_results)
                ? info.fold_results
                : [];

            if (folds.length) {
                const table = document.createElement("table");
                const header = document.createElement("tr");

                ["Held-out Configuration", "Samples", "Accuracy", "Class 1 F1"]
                    .forEach(label => {
                        const th = document.createElement("th");
                        th.textContent = label;
                        header.appendChild(th);
                    });

                table.appendChild(header);

                folds.forEach(fold => {
                    const row = document.createElement("tr");

                    [
                        fold.feeder,
                        fold.samples,
                        `${showNumber(fold.accuracy * 100)}%`,
                        showNumber(fold.class_1_f1)
                    ].forEach(value => {
                        const cell = document.createElement("td");
                        cell.textContent = String(value ?? "Unavailable");
                        row.appendChild(cell);
                    });

                    table.appendChild(row);
                });

                feederContainer.appendChild(table);
            } else {
                const message = document.createElement("p");
                message.textContent = "No feeder-wise fold results are available.";
                feederContainer.appendChild(message);
            }
        }

        if (thresholdContainer) {
            thresholdContainer.replaceChildren();

            const heading = document.createElement("h3");
            heading.textContent = "Exploratory threshold analysis";
            thresholdContainer.appendChild(heading);

            const thresholds = Array.isArray(info.threshold_analysis)
                ? info.threshold_analysis
                : [];

            if (thresholds.length) {
                const table = document.createElement("table");
                const header = document.createElement("tr");

                [
                    "Threshold",
                    "Precision",
                    "Recall",
                    "F1",
                    "False Negatives",
                    "False Positives"
                ].forEach(label => {
                    const th = document.createElement("th");
                    th.textContent = label;
                    header.appendChild(th);
                });

                table.appendChild(header);

                thresholds.forEach(item => {
                    const row = document.createElement("tr");

                    [
                        showNumber(item.threshold),
                        `${showNumber(item.precision * 100)}%`,
                        `${showNumber(item.recall * 100)}%`,
                        showNumber(item.f1),
                        item.false_negatives,
                        item.false_positives
                    ].forEach(value => {
                        const cell = document.createElement("td");
                        cell.textContent = String(value ?? "Unavailable");
                        row.appendChild(cell);
                    });

                    table.appendChild(row);
                });

                thresholdContainer.appendChild(table);
            } else {
                const message = document.createElement("p");
                message.textContent =
                    "No threshold comparison is available in the saved model.";
                thresholdContainer.appendChild(message);
            }
        }

        const limitations = Array.isArray(info.limitations)
            ? info.limitations
            : [];

        const note = document.getElementById("pqModelLimitations");

        if (note) {
            note.textContent = limitations.join(" ") ||
                "Model performance is based on simulated data and requires independent engineering validation.";
        }

    } catch (error) {
        loading.textContent =
            `PQ model metrics unavailable: ${error.message}`;
    }
}

// =============================================
// PQ SCREENING FORM
// =============================================

const pqForm = document.getElementById("pqForm");

if (pqForm) {
    pqForm.addEventListener("submit", async event => {
        event.preventDefault();

        const button = pqForm.querySelector('button[type="submit"]');
        const error = document.getElementById("pqError");

        if (!button || !error) return;

        error.textContent = "";

        const payload = {
            feeder_id: getValue("pqFeeder"),
            line_length_km: Number(getValue("pqLineLength")),
            line_r1: Number(getValue("pqR1")),
            line_x1: Number(getValue("pqX1")),
            phase_a_load_kw: Number(getValue("pqPhaseA")),
            phase_b_load_kw: Number(getValue("pqPhaseB")),
            phase_c_load_kw: Number(getValue("pqPhaseC"))
        };

        if (
            !payload.feeder_id ||
            !Number.isFinite(payload.line_length_km) ||
            payload.line_length_km <= 0 ||
            !Number.isFinite(payload.line_r1) ||
            payload.line_r1 <= 0 ||
            !Number.isFinite(payload.line_x1) ||
            payload.line_x1 <= 0 ||
            !Number.isFinite(payload.phase_a_load_kw) ||
            payload.phase_a_load_kw < 0 ||
            !Number.isFinite(payload.phase_b_load_kw) ||
            payload.phase_b_load_kw < 0 ||
            !Number.isFinite(payload.phase_c_load_kw) ||
            payload.phase_c_load_kw < 0
        ) {
            error.textContent =
                "Enter valid line parameters and non-negative phase loads.";
            return;
        }

        button.disabled = true;
        button.textContent = "Running PQ screening...";

        try {
            const data = await postJSON(API.pq, payload);
            displayPQResults(data);

        } catch (err) {
            error.textContent = err.message;

        } finally {
            button.disabled = false;
            button.textContent = "Run PQ Screening";
        }
    });
}

// =============================================
// DISPLAY PQ SCREENING RESULTS
// =============================================

function displayPQResults(result) {
    const resultElement = document.getElementById("pqResult");

    if (resultElement) resultElement.classList.remove("hidden");

    setText("pqStatus",
        (result.screening_status || "Unavailable").replaceAll("_", " "));

    setText("pqMessage", result.message);
    setText("pqClass",
        `${result.predicted_class} — ${result.class_label || "Unknown"}`);
    setText("pqScore",
        `${showNumber(result.class_1_model_score_percent)}%`);
    setText("pqThreshold",
        `${showNumber(result.screening_threshold_percent)}% VUF`);
    setText("pqValidation",
        result.validation_method || "Unavailable");

    fillList("pqLimitations", result.limitations);

    if (resultElement) {
        resultElement.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }
}

// =============================================
// OPENDSS SIMULATION CHARTS
// =============================================

let voltageChartInstance = null;
let transformerChartInstance = null;
let lineChartInstance = null;

async function loadSimulationCharts() {
    const status = document.getElementById("chartStatus");
    if (!status) return;

    try {
        if (typeof Chart === "undefined") {
            throw new Error("Chart.js did not load. Check your internet connection.");
        }

        const response = await fetch(API.hosting);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Unable to load simulation results.");
        }

        const records = data.simulation_results || [];

        const validRecords = records.filter(row =>
            row.result === "PASS" &&
            row.minimum_voltage_pu !== "" &&
            row.maximum_voltage_pu !== "" &&
            row.transformer_loading_percent !== "" &&
            row.line_loading_percent !== ""
        );

        if (!validRecords.length) {
            throw new Error("No valid passing simulation records are available.");
        }

        const sorted = validRecords.slice().sort(
            (a, b) => Number(a.solar_kw) - Number(b.solar_kw)
        );

        const solar = sorted.map(row => Number(row.solar_kw));

        function createChart(canvasId, existingInstance, datasets, yTitle) {
            if (existingInstance) existingInstance.destroy();

            const canvas = document.getElementById(canvasId);
            if (!canvas) return null;

            return new Chart(canvas, {
                type: "line",
                data: {
                    labels: solar,
                    datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: "Solar Generation (kW)"
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: yTitle
                            }
                        }
                    }
                }
            });
        }

        voltageChartInstance = createChart(
            "voltageChart",
            voltageChartInstance,
            [
                {
                    label: "Minimum Voltage (pu)",
                    data: sorted.map(row => Number(row.minimum_voltage_pu)),
                    borderColor: "#34d399",
                    tension: 0.3
                },
                {
                    label: "Maximum Voltage (pu)",
                    data: sorted.map(row => Number(row.maximum_voltage_pu)),
                    borderColor: "#60a5fa",
                    tension: 0.3
                }
            ],
            "Voltage (pu)"
        );

        transformerChartInstance = createChart(
            "transformerChart",
            transformerChartInstance,
            [{
                label: "Transformer Loading (%)",
                data: sorted.map(row => Number(row.transformer_loading_percent)),
                borderColor: "#a78bfa",
                tension: 0.3
            }],
            "Loading (%)"
        );

        lineChartInstance = createChart(
            "lineChart",
            lineChartInstance,
            [{
                label: "Distribution Line Loading (%)",
                data: sorted.map(row => Number(row.line_loading_percent)),
                borderColor: "#f59e0b",
                tension: 0.3
            }],
            "Loading (%)"
        );

        status.textContent =
            `Loaded ${validRecords.length} passing simulation records.`;

    } catch (error) {
        status.textContent = error.message;
        console.error(error);
    }
}

// =============================================
// LIVE WEATHER AND SOLAR DATA
// =============================================

async function loadLiveData() {
    const status = document.getElementById("liveDataStatus");
    if (!status) return;

    status.textContent = "Fetching live data...";

    try {
        const response = await fetch(API.liveData);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Unable to fetch live data.");
        }

        const weather = data.weather || {};

        setText("liveTemperature",
            `${showNumber(weather.temperature, 1)} °C`);
        setText("liveHumidity",
            `${showNumber(weather.humidity, 0)} %`);
        setText("liveCloudCover",
            `${showNumber(weather.cloud_cover, 0)} %`);
        setText("liveSolarRadiation",
            `${showNumber(weather.solar_radiation, 1)} W/m²`);

        status.textContent =
            `Live data connected · Source: ${data.source}`;

        const updated = data.timestamp
            ? new Date(data.timestamp).toLocaleString("en-IN", {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone: "Asia/Kolkata"
            })
            : "Unavailable";

        setText("liveDataUpdated", `Last updated: ${updated}`);

    } catch (error) {
        status.textContent =
            `Live data unavailable: ${error.message}`;

        console.error("Live data error:", error);
    }
}

const refreshLiveData = document.getElementById("refreshLiveData");

if (refreshLiveData) {
    refreshLiveData.addEventListener("click", async () => {
        refreshLiveData.disabled = true;
        refreshLiveData.textContent = "Refreshing...";

        try {
            await loadLiveData();
        } finally {
            refreshLiveData.disabled = false;
            refreshLiveData.textContent = "↻ Refresh";
        }
    });
}

// =============================================
// SOLAR GENERATION FORECAST
// =============================================

let solarForecastChart = null;

async function loadSolarForecast() {
    const status = document.getElementById("solarForecastStatus");
    const capacityInput = document.getElementById("solarCapacity");

    if (!status || !capacityInput) return;

    const capacity = Number(capacityInput.value);

    if (!Number.isFinite(capacity) || capacity <= 0) {
        status.textContent = "Enter a valid solar capacity.";
        return;
    }

    status.textContent = "Generating solar forecast...";

    try {
        const response = await fetch(
            `${API.solarForecast}?capacity_kw=${capacity}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Unable to generate forecast.");
        }

        setText("solarDailyEnergy",
            `${showNumber(data.estimated_total_energy_kwh)} kWh`);
        setText("solarInstalledCapacity",
            `${showNumber(data.capacity_kw, 1)} kW`);

        if (typeof Chart === "undefined") {
            throw new Error("Chart.js is not loaded.");
        }

        const forecast = data.forecast || [];

        const labels = forecast.map(item =>
            new Date(item.time).toLocaleTimeString("en-IN", {
                hour: "2-digit",
                minute: "2-digit",
                timeZone: "Asia/Kolkata"
            })
        );

        const generation = forecast.map(item =>
            Number(item.estimated_generation_kwh)
        );

        const canvas = document.getElementById("solarForecastChart");
        if (!canvas) return;

        if (solarForecastChart) solarForecastChart.destroy();

        solarForecastChart = new Chart(canvas, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Estimated Generation (kWh)",
                    data: generation,
                    borderColor: "#16a34a",
                    backgroundColor: "rgba(22,163,74,0.12)",
                    fill: true,
                    tension: 0.35,
                    pointRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: "Forecast Time"
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: "Energy (kWh)"
                        }
                    }
                }
            }
        });

        status.textContent =
            `Forecast generated successfully · ${data.location}`;

    } catch (error) {
        status.textContent =
            `Forecast unavailable: ${error.message}`;

        console.error("Solar forecast error:", error);
    }
}

const solarForecastButton = document.getElementById("loadSolarForecast");

if (solarForecastButton) {
    solarForecastButton.addEventListener("click", loadSolarForecast);
}

// =============================================
// HISTORICAL SOLAR PERFORMANCE ANALYTICS
// =============================================

let monthlySolarChartInstance = null;
let dailySolarChartInstance = null;

async function loadSolarAnalytics() {
    const status = document.getElementById("solarAnalyticsStatus");
    const capacityInput = document.getElementById("analyticsCapacity");
    const tariffInput = document.getElementById("electricityTariff");

    if (!status || !capacityInput || !tariffInput) return;

    const capacity = Number(capacityInput.value);
    const tariff = Number(tariffInput.value);

    if (
        !Number.isFinite(capacity) || capacity <= 0 ||
        !Number.isFinite(tariff) || tariff < 0
    ) {
        status.textContent =
            "Enter valid capacity and electricity tariff.";
        return;
    }

    status.textContent = "Loading historical solar analytics...";

    try {
        const response = await fetch(
            `${API.solarAnalytics}?year=2025&capacity_kw=${capacity}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Unable to load solar analytics.");
        }

        const monthly = data.monthly_analytics || [];

        if (monthly.length !== 12) {
            throw new Error("Incomplete monthly analytics received.");
        }

        const annualEnergy = Number(data.estimated_annual_energy_kwh);
        const averageMonthly = annualEnergy / 12;

        setText("analyticsAnnualEnergy",
            `${showNumber(annualEnergy)} kWh`);
        setText("analyticsMonthlyEnergy",
            `${showNumber(averageMonthly)} kWh`);
        setText("analyticsAnnualSavings",
            `₹ ${showNumber(annualEnergy * tariff, 0)}`);

        const installationCostInput =
            document.getElementById("solarInstallationCost");

        const installationCost = installationCostInput
            ? Number(installationCostInput.value)
            : NaN;

        if (!Number.isFinite(installationCost) || installationCost <= 0) {
            throw new Error("Enter a valid installation cost.");
        }

        const annualSavings = annualEnergy * tariff;
        const paybackYears = annualSavings > 0
            ? installationCost / annualSavings
            : null;

        const fiveYearBenefit = annualSavings * 5 - installationCost;
        const tenYearBenefit = annualSavings * 10 - installationCost;

        setText("solarPaybackPeriod",
            paybackYears !== null
                ? `${showNumber(paybackYears, 2)} Years`
                : "Unavailable");

        setText("solarFiveYearBenefit",
            `₹ ${showNumber(fiveYearBenefit, 0)}`);
        setText("solarTenYearBenefit",
            `₹ ${showNumber(tenYearBenefit, 0)}`);
        setText("analyticsInstalledCapacity",
            `${showNumber(data.capacity_kw, 1)} kW`);

        const labels = monthly.map(item => item.month);
        const monthlyValues = monthly.map(
            item => Number(item.estimated_energy_kwh)
        );
        const dailyValues = monthly.map(
            item => Number(item.average_daily_energy_kwh)
        );

        const monthlyCanvas = document.getElementById("monthlySolarChart");

        if (monthlyCanvas) {
            if (monthlySolarChartInstance) {
                monthlySolarChartInstance.destroy();
            }

            monthlySolarChartInstance = new Chart(monthlyCanvas, {
                type: "bar",
                data: {
                    labels,
                    datasets: [{
                        label: "Estimated Energy (kWh)",
                        data: monthlyValues,
                        backgroundColor: "#16a34a",
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { display: true }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: "Energy (kWh)"
                            }
                        }
                    }
                }
            });
        }

        const dailyCanvas = document.getElementById("dailySolarChart");

        if (dailyCanvas) {
            if (dailySolarChartInstance) {
                dailySolarChartInstance.destroy();
            }

            dailySolarChartInstance = new Chart(dailyCanvas, {
                type: "line",
                data: {
                    labels,
                    datasets: [{
                        label: "Average Daily Energy (kWh)",
                        data: dailyValues,
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59,130,246,0.12)",
                        fill: true,
                        tension: 0.35
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: "Energy (kWh)"
                            }
                        }
                    }
                }
            });
        }

        status.textContent =
            `Historical solar analytics loaded successfully · ` +
            `${data.location} · Year ${data.historical_year}`;

    } catch (error) {
        status.textContent =
            `Analytics unavailable: ${error.message}`;

        console.error("Solar analytics error:", error);
    }
}

const solarAnalyticsButton = document.getElementById("loadSolarAnalytics");

if (solarAnalyticsButton) {
    solarAnalyticsButton.addEventListener("click", loadSolarAnalytics);
}

// =========================================
// ENERGY ADVISOR FRONTEND
// =========================================

async function loadEnergyAdvisor(event) {
    event.preventDefault();

    const errorElement = document.getElementById("energyAdvisorError");
    const resultElement = document.getElementById("energyAdvisorResult");

    if (!errorElement || !resultElement) return;

    errorElement.textContent = "";
    resultElement.classList.add("hidden");

    const capacity = Number(document.getElementById("advisorCapacity").value);
    const tariff = Number(document.getElementById("advisorTariff").value);

    if (!Number.isFinite(capacity) || capacity <= 0 || capacity > 1000) {
        errorElement.textContent = "Enter a valid solar capacity.";
        return;
    }

    if (!Number.isFinite(tariff) || tariff < 0 || tariff > 100) {
        errorElement.textContent = "Enter a valid electricity tariff.";
        return;
    }

    const submitButton = document.querySelector(
        "#energyAdvisorForm button[type='submit']"
    );

    if (!submitButton) return;

    submitButton.disabled = true;
    submitButton.textContent = "Generating advice...";

    try {
        const data = await postJSON(API.energyAdvisor, {
            capacity_kw: capacity,
            electricity_tariff: tariff
        });

        resultElement.classList.remove("hidden");

        setText("energyAdvisorTitle",
            "Energy Recommendations Generated");

        setText("energyAdvisorSummary",
            `Location: ${data.location} | Advisor: ${data.advisor_type}`);

        setText("advisorDailyEnergy",
            `${showNumber(data.estimated_forecast_energy_kwh, 2)} kWh`);

        setText("advisorEnergyValue",
            `₹ ${showNumber(data.estimated_energy_value_inr, 2)}`);

        setText("advisorCapacityResult",
            `${showNumber(data.installation_capacity_kw, 2)} kW`);

        setText("advisorTariffResult",
            `₹ ${showNumber(data.electricity_tariff_inr_per_kwh, 2)} / kWh`);

        function displayAdvisorList(elementId, items) {
            const list = document.getElementById(elementId);
            if (!list) return;

            list.replaceChildren();

            if (!Array.isArray(items) || items.length === 0) {
                const item = document.createElement("li");
                item.textContent = "No information available.";
                list.appendChild(item);
                return;
            }

            items.forEach(text => {
                const item = document.createElement("li");
                item.textContent = text;
                list.appendChild(item);
            });
        }

        displayAdvisorList("advisorWeatherObservations", data.weather_observations);
        displayAdvisorList("advisorRecommendations", data.recommendations);
        displayAdvisorList("advisorLimitations", data.limitations);

        const comparisonContainer =
            document.getElementById("advisorCapacityComparison");

        if (comparisonContainer) {
            comparisonContainer.replaceChildren();

            if (Array.isArray(data.capacity_comparison)) {
                data.capacity_comparison.forEach(item => {
                    const row = document.createElement("div");
                    row.className = "result-item";

                    const heading = document.createElement("h3");
                    heading.textContent = `${item.capacity_kw} kW System`;

                    const energy = document.createElement("p");
                    energy.textContent =
                        `Estimated generation: ${showNumber(item.estimated_energy_kwh, 2)} kWh`;

                    const value = document.createElement("p");
                    value.textContent =
                        `Estimated energy value: ₹ ${showNumber(item.estimated_energy_value_inr, 2)}`;

                    row.append(heading, energy, value);
                    comparisonContainer.appendChild(row);
                });
            }
        }

        resultElement.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    } catch (error) {
        errorElement.textContent = error.message;

    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Generate Energy Advice →";
    }
}

const energyAdvisorForm = document.getElementById("energyAdvisorForm");

if (energyAdvisorForm) {
    energyAdvisorForm.addEventListener("submit", loadEnergyAdvisor);
}

// =========================================
// INITIALIZE SYSTEM MONITORING
// =========================================

loadSystemMonitoring();

setInterval(() => {
    loadSystemMonitoring();
}, 60000);

// =========================================
// GRIDSENSE PROJECT INTELLIGENCE
// =========================================

async function loadProjectIntelligence() {

    // 1. SOLAR GENERATION INSIGHT

    try {
        const response = await fetch(`${API.solarForecast}?capacity_kw=10`);

        if (!response.ok) throw new Error("Solar forecast unavailable");

        const data = await response.json();
        const energy = Number(data.estimated_total_energy_kwh);

        setText("intelligenceSolarEnergy", `${showNumber(energy, 2)} kWh`);

        setText("solarInsight",
            `A 10 kW solar system has an estimated generation of ${showNumber(energy, 2)} kWh over the next 24 hours. This is a weather-based estimate, not measured production.`);

    } catch (error) {
        setText("intelligenceSolarEnergy", "Unavailable");
        setText("solarInsight",
            "Solar forecast is currently unavailable. Check the weather service.");
    }

    // 2. HOSTING CAPACITY INSIGHT

    try {
        const response = await fetch(API.hosting);

        if (response.status === 404) {
            setText("intelligenceHostingStatus", "NO DATA");
            setText("hostingInsight",
                "No hosting simulation records are currently available. Run an engineering assessment first.");

        } else if (!response.ok) {
            throw new Error("Hosting results unavailable");

        } else {
            const data = await response.json();
            const count = Number(data.total_records || 0);

            setText("intelligenceHostingStatus",
                count > 0 ? "AVAILABLE" : "NO DATA");

            setText("hostingInsight",
                count > 0
                    ? `${count} hosting simulation records are available. Review the Engineering Assessment and Analytics pages for feeder-level results.`
                    : "No hosting simulation records are currently available. Run an engineering assessment first.");
        }

    } catch (error) {
        setText("intelligenceHostingStatus", "UNAVAILABLE");
        setText("hostingInsight",
            "Hosting results could not be retrieved from the backend.");
    }

    // 3. POWER QUALITY INSIGHT

    try {
        const response = await fetch(API.pqInfo);

        if (!response.ok) throw new Error("PQ model unavailable");

        const data = await response.json();

        setText("intelligencePQStatus", "READY");

        setText("pqInsight",
            `The power-quality screening model is available. Model type: ${data.model_type || "PQ screening classifier"}. Run PQ Screening to evaluate a feeder configuration.`);

    } catch (error) {
        setText("intelligencePQStatus", "OFFLINE");
        setText("pqInsight",
            "The PQ screening model is unavailable. Check model availability before running screening.");
    }

    // 4. ENERGY ADVISOR INSIGHT

    try {
        const data = await postJSON(API.energyAdvisor, {
            capacity_kw: 10,
            electricity_tariff: 8
        });

        setText("intelligenceEnergyStatus", "READY");

        const firstRecommendation =
            Array.isArray(data.recommendations) &&
            data.recommendations.length > 0
                ? data.recommendations[0]
                : "No recommendations available.";

        setText("energyInsight", firstRecommendation);

    } catch (error) {
        setText("intelligenceEnergyStatus", "OFFLINE");
        setText("energyInsight",
            "Energy Advisor is currently unavailable. Check the weather and solar forecast services.");
    }

    await loadIntelligenceActivity();
}

// =========================================
// RECENT ASSESSMENT ACTIVITY
// =========================================

async function loadIntelligenceActivity() {
    const status = document.getElementById("intelligenceActivityStatus");
    const container = document.getElementById("intelligenceActivityList");

    if (!status || !container) return;

    try {
        const response = await fetch(
            `${API_BASE}/assessment-history?skip=0&limit=5`
        );

        if (!response.ok) throw new Error("Assessment history unavailable");

        const data = await response.json();

        container.replaceChildren();

        const records = data.assessments || [];

        if (records.length === 0) {
            status.textContent = "No saved assessments yet.";
            return;
        }

        status.textContent = `${data.total_records} total saved assessments`;

        records.forEach(record => {
            const item = document.createElement("div");
            item.className = "result-item";

            const heading = document.createElement("h3");
            heading.textContent = record.assessment_type || "Assessment";

            const details = document.createElement("p");
            details.textContent =
                `Feeder: ${record.feeder_code || "N/A"} | Status: ${record.status || "N/A"}`;

            const date = document.createElement("p");
            date.textContent = record.created_at
                ? `Date: ${new Date(record.created_at).toLocaleString()}`
                : "Date unavailable";

            item.append(heading, details, date);
            container.appendChild(item);
        });

    } catch (error) {
        status.textContent = "Unable to load assessment history.";
        container.replaceChildren();
    }
}

// =========================================
// REFRESH PROJECT INTELLIGENCE
// =========================================

const intelligenceRefresh = document.getElementById("refreshIntelligence");

if (intelligenceRefresh) {
    intelligenceRefresh.addEventListener("click", async () => {
        intelligenceRefresh.disabled = true;
        intelligenceRefresh.textContent = "Refreshing...";

        try {
            await loadProjectIntelligence();
        } finally {
            intelligenceRefresh.disabled = false;
            intelligenceRefresh.textContent = "↻ Refresh Intelligence";
        }
    });
}

// =========================================
// UNIFIED SOLAR PERFORMANCE ANALYTICS
// =========================================

async function loadUnifiedSolarPerformance() {
    const status = document.getElementById("unifiedSolarStatus");
    const annualElement = document.getElementById("unifiedAnnualEnergy");
    const averageElement = document.getElementById("unifiedMonthlyAverage");

    if (!status || !annualElement || !averageElement) return;

    status.textContent = "Loading historical solar analytics...";

    try {
        const response = await fetch(
            `${API.solarAnalytics}?year=2025&capacity_kw=10`
        );

        if (!response.ok) {
            throw new Error("Historical solar analytics unavailable.");
        }

        const data = await response.json();

        const annualEnergy = Number(data.estimated_annual_energy_kwh);
        const monthlyData = data.monthly_analytics;

        if (
            !Number.isFinite(annualEnergy) ||
            !Array.isArray(monthlyData) ||
            monthlyData.length !== 12
        ) {
            throw new Error("Invalid historical solar analytics data.");
        }

        const monthlyLabels = monthlyData.map(item => item.month);
        const monthlyEnergy = monthlyData.map(
            item => Number(item.estimated_energy_kwh)
        );

        if (!monthlyEnergy.every(Number.isFinite)) {
            throw new Error("Invalid monthly generation values.");
        }

        setText("unifiedAnnualEnergy",
            `${showNumber(annualEnergy, 2)} kWh`);

        setText("unifiedMonthlyAverage",
            `${showNumber(annualEnergy / 12, 2)} kWh`);

        const canvas = document.getElementById("unifiedSolarChart");
        if (!canvas) return;

        if (window.unifiedSolarChart instanceof Chart) {
            window.unifiedSolarChart.destroy();
        }

        window.unifiedSolarChart = new Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: monthlyLabels,
                datasets: [{
                    label: "Estimated Solar Generation (kWh)",
                    data: monthlyEnergy,
                    backgroundColor: "#27a879",
                    borderRadius: 7,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: "Energy (kWh)"
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: "Month"
                        }
                    }
                }
            }
        });

        status.textContent =
            "Historical solar analytics loaded successfully. Data year: 2025 | Capacity: 10 kW.";

    } catch (error) {
        status.textContent = error.message;
        setText("unifiedAnnualEnergy", "Unavailable");
        setText("unifiedMonthlyAverage", "Unavailable");
    }
}

// =========================================
// UNIFIED ASSESSMENT REPORT
// =========================================

async function loadUnifiedReport() {
    const status = document.getElementById("reportStatus");
    const container = document.getElementById("unifiedReportList");

    if (!status || !container) return;

    status.textContent = "Loading assessment records...";

    try {
        const response = await fetch(
            `${API_BASE}/assessment-history?skip=0&limit=10`
        );

        if (!response.ok) {
            throw new Error("Unable to retrieve assessment history.");
        }

        const data = await response.json();
        const records = data.assessments || [];

        setText("reportTotalAssessments", data.total_records ?? 0);
        container.replaceChildren();

        if (records.length === 0) {
            setText("reportLatestType", "None");
            setText("reportLatestDate", "No saved records");
            status.textContent = "No assessment records found.";
            return;
        }

        const latest = records[0];

        setText("reportLatestType",
            latest.assessment_type || "Assessment");

        setText("reportLatestDate",
            latest.created_at
                ? new Date(latest.created_at).toLocaleString()
                : "Date unavailable");

        records.forEach(record => {
            const card = document.createElement("article");
            card.className = "result-item";

            const heading = document.createElement("h3");
            heading.textContent = record.assessment_type || "Assessment";

            const feeder = document.createElement("p");
            feeder.textContent = `Feeder: ${record.feeder_code || "N/A"}`;

            const recordStatus = document.createElement("p");
            recordStatus.textContent = `Status: ${record.status || "N/A"}`;

            const date = document.createElement("p");
            date.textContent = record.created_at
                ? new Date(record.created_at).toLocaleString()
                : "Date unavailable";

            const details = document.createElement("button");
            details.type = "button";
            details.className = "overview-primary-action";
            details.textContent = "View assessment";

            details.addEventListener("click", () => {
                window.open(
                    `${API_BASE}/assessment-history/${encodeURIComponent(record.id)}`,
                    "_blank",
                    "noopener,noreferrer"
                );
            });

            card.append(heading, feeder, recordStatus, date, details);
            container.appendChild(card);
        });

        status.textContent = `Showing ${records.length} recent records.`;

    } catch (error) {
        status.textContent = error.message;
        container.replaceChildren();
    }
}

// =========================================
// REFRESH REPORT BUTTON
// =========================================

const reportRefreshButton = document.getElementById("refreshReport");

if (reportRefreshButton) {
    reportRefreshButton.addEventListener("click", async () => {
        reportRefreshButton.disabled = true;
        reportRefreshButton.textContent = "Refreshing...";

        try {
            await loadUnifiedReport();
        } finally {
            reportRefreshButton.disabled = false;
            reportRefreshButton.textContent = "↻ Refresh Report";
        }
    });
}

// =========================================
// EXPORT ASSESSMENT REPORT CSV
// =========================================

async function exportAssessmentReportCSV() {
    try {
        const response = await fetch(
            `${API_BASE}/assessment-history?skip=0&limit=1000`
        );

        if (!response.ok) {
            throw new Error("Unable to export assessment records.");
        }

        const data = await response.json();
        const records = data.assessments || [];

        if (records.length === 0) {
            alert("No assessment records available to export.");
            return;
        }

        const headers = [
            "ID",
            "Assessment Type",
            "Feeder Code",
            "Status",
            "Created At"
        ];

        const escapeCSV = value =>
            `"${String(value ?? "").replace(/"/g, '""')}"`;

        const rows = records.map(record => [
            record.id,
            record.assessment_type,
            record.feeder_code,
            record.status,
            record.created_at
        ]);

        const csvContent = [headers, ...rows]
            .map(row => row.map(escapeCSV).join(","))
            .join("\n");

        const blob = new Blob(["\uFEFF" + csvContent], {
            type: "text/csv;charset=utf-8;"
        });

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = "GridSense_Assessment_Report.csv";

        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(url);

    } catch (error) {
        alert(error.message);
    }
}

const exportReportButton = document.getElementById("exportReportCSV");

if (exportReportButton) {
    exportReportButton.addEventListener("click", exportAssessmentReportCSV);
}

// =========================================
// REFRESH OVERVIEW DASHBOARD
// =========================================

async function refreshOverviewDashboard() {
    const button = document.getElementById("refreshOverview");

    if (button) {
        button.disabled = true;
        button.textContent = "Refreshing...";
    }

    const refreshTasks = [
        checkBackend(),
        loadSystemMonitoring(),
        loadPQModelInfo(),
        loadSimulationCharts(),
        loadLiveData(),
        loadSolarForecast(),
        loadSolarAnalytics(),
        loadProjectIntelligence(),
        loadUnifiedSolarPerformance(),
        loadUnifiedReport()
    ];

    try {
        await Promise.allSettled(refreshTasks);
        updateOverviewTimestamp();

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "↻ Refresh Dashboard";
        }
    }
}

const refreshOverviewButton = document.getElementById("refreshOverview");

if (refreshOverviewButton) {
    refreshOverviewButton.addEventListener("click", refreshOverviewDashboard);
}

// =========================================
// OVERVIEW LAST UPDATED TIMESTAMP
// =========================================

function updateOverviewTimestamp() {
    const timestamp = document.getElementById("overviewLastUpdated");
    if (!timestamp) return;

    timestamp.textContent =
        "Last updated: " + new Date().toLocaleString();
}

// =========================================
// INITIALIZE DASHBOARD
// =========================================

async function initializeDashboard() {
    const isOverviewPage =
        document.getElementById("overviewLastUpdated") ||
        document.getElementById("unifiedReportList") ||
        document.getElementById("intelligenceSolarEnergy");

    if (!isOverviewPage) return;

    await Promise.allSettled([
        checkBackend(),
        loadSystemMonitoring(),
        loadPQModelInfo(),
        loadSimulationCharts(),
        loadLiveData(),
        loadSolarForecast(),
        loadSolarAnalytics(),
        loadProjectIntelligence(),
        loadUnifiedSolarPerformance(),
        loadUnifiedReport()
    ]);

    updateOverviewTimestamp();
}

initializeDashboard();

// =============================================
// AUTOMATIC LIVE DATA REFRESH — EVERY 5 MINUTES
// =============================================

const LIVE_REFRESH_INTERVAL = 5 * 60 * 1000;

if (document.getElementById("liveDataStatus")) {
    setInterval(() => {
        if (!document.hidden) loadLiveData();
    }, LIVE_REFRESH_INTERVAL);

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) loadLiveData();
    });
}

// =============================================
// SUBTLE POINTER DETAIL (DESKTOP ONLY)
// =============================================

(function initPointerDetail() {
    if (window.matchMedia("(pointer: fine)").matches) {
        const pointer = document.createElement("span");
        pointer.className = "gs-pointer";

        document.body.appendChild(pointer);

        document.addEventListener("pointermove", event => {
            pointer.style.left = `${event.clientX}px`;
            pointer.style.top = `${event.clientY}px`;
        });
    }
})();

// =============================================
// INITIALIZE ANALYTICS PAGE
// =============================================

if (document.getElementById("chartStatus")) {
    loadSimulationCharts();
}

// ==========================================
// GRIDSENSE AI CHATBOT - GEMINI INTEGRATION
// ==========================================

let chatHistory = [];

const chatForm = document.getElementById("chatForm");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const chatError = document.getElementById("chatError");
const chatSendButton = document.getElementById("chatSendButton");
const chatClearButton = document.getElementById("chatClearButton");

// Convert backend errors into readable messages

function getReadableChatError(detail) {
    if (typeof detail === "string") {
        return detail;
    }

    if (Array.isArray(detail)) {
        return detail.map(item => {
            if (typeof item === "string") return item;

            const location = Array.isArray(item.loc)
                ? item.loc.join(" → ")
                : "";

            return `${location ? location + ": " : ""}${item.msg || JSON.stringify(item)}`;
        }).join("\n");
    }

    if (detail && typeof detail === "object") {
        return detail.message ||
            detail.msg ||
            detail.error ||
            JSON.stringify(detail, null, 2);
    }

    return "An unexpected error occurred.";
}

// Extract AI reply from backend response

function getGeminiReply(data) {
    const possibleReplies = [
        data.reply,
        data.response,
        data.answer,
        data.message,
        data.output,
        data.text
    ];

    for (const item of possibleReplies) {
        if (typeof item === "string" && item.trim()) {
            return item;
        }

        if (item && typeof item === "object") {
            const nested =
                item.text ||
                item.reply ||
                item.message ||
                item.content;

            if (typeof nested === "string" && nested.trim()) {
                return nested;
            }
        }
    }

    return null;
}

// Display chat messages

function addChatMessage(role, message) {
    if (!chatMessages) return;

    const messageDiv = document.createElement("div");

    messageDiv.className =
        role === "user"
            ? "chat-message user-message"
            : "chat-message assistant-message";

    const heading = document.createElement("strong");

    heading.textContent =
        role === "user" ? "You" : "GridSense AI";

    const paragraph = document.createElement("p");
    paragraph.textContent = String(message);

    messageDiv.append(heading, paragraph);

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Initialize chatbot

if (chatForm && chatMessages && chatInput) {

    chatForm.addEventListener("submit", async event => {
        event.preventDefault();

        const message = chatInput.value.trim();

        if (!message) return;

        if (chatError) chatError.textContent = "";

        addChatMessage("user", message);

        chatInput.value = "";
        chatInput.disabled = true;

        if (chatSendButton) {
            chatSendButton.disabled = true;
            chatSendButton.textContent = "Thinking...";
        }

        const loadingMessage = document.createElement("div");

        loadingMessage.className =
            "chat-message assistant-message";

        loadingMessage.textContent =
            "GridSense AI is thinking...";

        chatMessages.appendChild(loadingMessage);

        chatMessages.scrollTop = chatMessages.scrollHeight;

        try {
            const response = await fetch(API.chat, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: message,
                    history: chatHistory
                })
            });

            const responseText = await response.text();

            let data;

            try {
                data = responseText
                    ? JSON.parse(responseText)
                    : {};
            } catch {
                throw new Error(
                    "Backend returned an invalid response. Check FastAPI."
                );
            }

            if (!response.ok) {
                const detail = data.detail || data.message || data;

                throw new Error(
                    getReadableChatError(detail)
                );
            }

            const reply = getGeminiReply(data);

            if (!reply) {
                console.error("Unexpected Gemini response:", data);

                throw new Error(
                    "Gemini responded, but no reply text was found. Check the /chat backend response."
                );
            }

            loadingMessage.remove();

            addChatMessage("assistant", reply);

            // Save conversation history

            chatHistory.push(
                {
                    role: "user",
                    content: message
                },
                {
                    role: "model",
                    content: reply
                }
            );

        } catch (error) {
            loadingMessage.remove();

            if (chatError) {
                chatError.textContent =
                    "Error: " + getReadableChatError(error.message);
            }

            console.error(
                "GridSense Gemini chatbot error:",
                error
            );

        } finally {
            chatInput.disabled = false;

            if (chatSendButton) {
                chatSendButton.disabled = false;
                chatSendButton.textContent = "Send";
            }

            chatInput.focus();
        }
    });

    // Clear conversation

    if (chatClearButton) {
        chatClearButton.addEventListener("click", () => {
            chatHistory = [];

            chatMessages.replaceChildren();

            if (chatError) {
                chatError.textContent = "";
            }

            addChatMessage(
                "assistant",
                "Hi! I'm your GridSense assistant. Ask me anything about renewable energy and electrical distribution networks."
            );
        });
    }
}
