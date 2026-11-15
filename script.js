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
    energyAdvisor: `${API_BASE}/energy-advisor`
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
            throw new Error(
                data.detail || `Request failed (${response.status})`
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

        if (status) {
            status.textContent = "Connected";
        }

        if (backendStatus) {
            backendStatus.textContent = "ONLINE";
        }

    } catch (error) {
        if (status) {
            status.textContent = "Disconnected";
        }

        if (backendStatus) {
            backendStatus.textContent = "OFFLINE";
        }
    }
}

// =============================================
// MODULE AVAILABILITY CHECKS
// =============================================

async function loadSystemMonitoring() {
    await Promise.all([
        checkModuleStatus(
            API.hosting,
            "engineeringStatus"
        ),

        // AI advisory is POST-only.
        // Use the health endpoint for the availability check.
        checkModuleStatus(
            API.health,
            "aiModuleStatus"
        ),

        checkModuleStatus(
            API.pqInfo,
            "pqModuleStatus"
        )
    ]);
}

// =============================================
// ENGINEERING CONNECTION ASSESSMENT
// =============================================

const engineeringForm =
    document.getElementById("engineeringForm");

if (engineeringForm) {
    engineeringForm.addEventListener("submit", async event => {
        event.preventDefault();

        const button =
            engineeringForm.querySelector('button[type="submit"]');

        const error =
            document.getElementById("engineeringError");

        error.textContent = "";

        const feederId = getValue("engineeringFeeder");

        const requestedSolar =
            Number(getValue("requestedSolar"));

        if (
            !feederId ||
            !Number.isFinite(requestedSolar) ||
            requestedSolar <= 0
        ) {
            error.textContent =
                "Enter a valid feeder ID and solar capacity.";
            return;
        }

        button.disabled = true;
        button.textContent = "Assessing...";

        try {
            const data = await postJSON(
                API.connection,
                {
                    feeder_id: feederId,
                    requested_solar_kw: requestedSolar
                }
            );

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

    document
        .getElementById("engineeringResult")
        .classList.remove("hidden");

    setText(
        "engineeringStatus",
        (result.status || "Unavailable").replaceAll("_", " ")
    );

    setText(
        "engineeringMessage",
        result.message
    );

    setText(
        "existingSolar",
        `${showNumber(result.existing_solar_kw)} kW`
    );

    setText(
        "newSolar",
        `${showNumber(result.requested_new_solar_kw)} kW`
    );

    setText(
        "totalSolar",
        `${showNumber(result.proposed_total_solar_kw)} kW`
    );

    setText(
        "headroom",
        `${showNumber(result.demonstrated_additional_headroom_kw)} kW`
    );

    setText(
        "limitingFactor",
        result.first_limiting_factor
    );

    document
        .getElementById("engineeringResult")
        .scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
}

// =============================================
// AI HOSTING CAPACITY ADVISORY
// =============================================

const aiForm = document.getElementById("aiForm");

if (aiForm) {
    aiForm.addEventListener("submit", async event => {
        event.preventDefault();

        const button =
            aiForm.querySelector('button[type="submit"]');

        const error =
            document.getElementById("aiError");

        error.textContent = "";

        const payload = {
            feeder_id: getValue("aiFeeder"),

            peak_load_kw:
                Number(getValue("peakLoad")),

            line_length_km:
                Number(getValue("aiLineLength")),

            existing_solar_kw:
                Number(getValue("existingSolarInput")),

            requested_solar_kw:
                Number(getValue("aiRequestedSolar"))
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
            error.textContent =
                "Please enter valid feeder and solar details.";
            return;
        }

        button.disabled = true;
        button.textContent = "Running AI models...";

        try {
            const data = await postJSON(
                API.ai,
                payload
            );

            displayAIResults(
                data.ai_advisory || {}
            );

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
    document
        .getElementById("aiResult")
        .classList.remove("hidden");

    setText(
        "aiStatus",
        (result.status || "Unavailable").replaceAll("_", " ")
    );

    setText(
        "aiMessage",
        result.explanation || "No explanation returned."
    );

    const regression =
        result.regression_prediction || {};

    const classification =
        result.classification_prediction || {};

    const inputs =
        result.inputs || {};

    setText(
        "predictedCapacity",
        `${showNumber(
            regression.estimated_additional_hosting_capacity_kw
        )} kW`
    );

    setText(
        "constraintClass",
        `Class ${classification.predicted_class ?? "Unavailable"}`
    );

    const class1Score =
        classification.configured_violation_model_score_percent ??
        classification.configured_violation_probability_percent;

    setText(
        "constraintScore",
        class1Score !== undefined && class1Score !== null
            ? `${showNumber(class1Score)}%`
            : "Unavailable"
    );

    setText(
        "aiTotalSolar",
        `${showNumber(inputs.proposed_total_solar_kw)} kW`
    );

    fillList(
        "aiLimitations",
        result.limitations
    );

    document
        .getElementById("aiResult")
        .scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
}
// =============================================
// PQ FEEDER CONFIGURATION PRESETS
// =============================================

const pqPresets = {
    FDR_SHORT: {
        length: 0.2,
        r1: 0.05,
        x1: 0.04
    },

    FDR_MEDIUM: {
        length: 0.5,
        r1: 0.05,
        x1: 0.04
    },

    FDR_LONG: {
        length: 1.0,
        r1: 0.05,
        x1: 0.04
    },

    FDR_HIGH_IMPEDANCE: {
        length: 2.0,
        r1: 0.10,
        x1: 0.08
    }
};

const pqFeeder =
    document.getElementById("pqFeeder");

if (pqFeeder) {
    pqFeeder.addEventListener("change", () => {
        const preset = pqPresets[pqFeeder.value];

        if (!preset) return;

        document.getElementById("pqLineLength").value =
            preset.length;

        document.getElementById("pqR1").value =
            preset.r1;

        document.getElementById("pqX1").value =
            preset.x1;
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

    card.append(
        heading,
        valueElement
    );

    return card;
}

// =============================================
// LOAD SAVED PQ MODEL EVALUATION
// =============================================

async function loadPQModelInfo() {
    const loading =
        document.getElementById("pqModelLoading");

    const cards =
        document.getElementById("pqMetricCards");

    const feederContainer =
        document.getElementById("pqFeederValidation");

    const thresholdContainer =
        document.getElementById("pqThresholdAnalysis");

    if (!loading || !cards) return;

    try {
        const response = await fetch(API.pqInfo);
        const info = await response.json();

        if (!response.ok) {
            throw new Error(
                info.detail ||
                "Could not load PQ model information."
            );
        }

        const evaluation =
            info.evaluation || {};

        // PERFORMANCE CARDS

        cards.replaceChildren(
            makeMetricCard(
                "LOFO Accuracy",
                `${showNumber(evaluation.accuracy * 100)}%`
            ),

            makeMetricCard(
                "Balanced Accuracy",
                `${showNumber(evaluation.balanced_accuracy * 100)}%`
            ),

            makeMetricCard(
                "Class 1 Precision",
                `${showNumber(evaluation.class_1_precision * 100)}%`
            ),

            makeMetricCard(
                "Class 1 Recall",
                `${showNumber(evaluation.class_1_recall * 100)}%`
            ),

            makeMetricCard(
                "Class 1 F1",
                `${showNumber(evaluation.class_1_f1 * 100)}%`
            ),

            makeMetricCard(
                "Decision Threshold",
                showNumber(info.decision_threshold)
            )
        );

        loading.textContent =
            `Validation: ${info.validation_method || "Not reported"}. ` +
            "These are out-of-fold metrics on simulated configurations.";

        // FEEDER-WISE VALIDATION

        feederContainer.replaceChildren();

        const feederHeading =
            document.createElement("h3");

        feederHeading.textContent =
            "Feeder-wise validation";

        feederContainer.appendChild(feederHeading);

        const folds =
            Array.isArray(info.fold_results)
                ? info.fold_results
                : [];

        if (folds.length) {
            const table =
                document.createElement("table");

            const header =
                document.createElement("tr");

            [
                "Held-out Configuration",
                "Samples",
                "Accuracy",
                "Class 1 F1"
            ].forEach(label => {
                const th =
                    document.createElement("th");

                th.textContent = label;
                header.appendChild(th);
            });

            table.appendChild(header);

            folds.forEach(fold => {
                const row =
                    document.createElement("tr");

                [
                    fold.feeder,
                    fold.samples,
                    `${showNumber(fold.accuracy * 100)}%`,
                    showNumber(fold.class_1_f1)
                ].forEach(value => {
                    const cell =
                        document.createElement("td");

                    cell.textContent =
                        String(value ?? "Unavailable");

                    row.appendChild(cell);
                });

                table.appendChild(row);
            });

            feederContainer.appendChild(table);

        } else {
            const message =
                document.createElement("p");

            message.textContent =
                "No feeder-wise fold results are available.";

            feederContainer.appendChild(message);
        }

        // THRESHOLD ANALYSIS

        thresholdContainer.replaceChildren();

        const thresholdHeading =
            document.createElement("h3");

        thresholdHeading.textContent =
            "Exploratory threshold analysis";

        thresholdContainer.appendChild(thresholdHeading);

        const thresholds =
            Array.isArray(info.threshold_analysis)
                ? info.threshold_analysis
                : [];

        if (thresholds.length) {
            const table =
                document.createElement("table");

            const header =
                document.createElement("tr");

            [
                "Threshold",
                "Precision",
                "Recall",
                "F1",
                "False Negatives",
                "False Positives"
            ].forEach(label => {
                const th =
                    document.createElement("th");

                th.textContent = label;
                header.appendChild(th);
            });

            table.appendChild(header);

            thresholds.forEach(item => {
                const row =
                    document.createElement("tr");

                [
                    showNumber(item.threshold),
                    `${showNumber(item.precision * 100)}%`,
                    `${showNumber(item.recall * 100)}%`,
                    showNumber(item.f1),
                    item.false_negatives,
                    item.false_positives
                ].forEach(value => {
                    const cell =
                        document.createElement("td");

                    cell.textContent =
                        String(value ?? "Unavailable");

                    row.appendChild(cell);
                });

                table.appendChild(row);
            });

            thresholdContainer.appendChild(table);

        } else {
            const message =
                document.createElement("p");

            message.textContent =
                "No threshold comparison is available in the saved model.";

            thresholdContainer.appendChild(message);
        }

        // LIMITATIONS

        const limitations =
            Array.isArray(info.limitations)
                ? info.limitations
                : [];

        const note =
            document.getElementById("pqModelLimitations");

        if (note) {
            note.textContent =
                limitations.join(" ") ||
                "Model performance is based on simulated data and " +
                "requires independent engineering validation.";
        }

    } catch (error) {
        loading.textContent =
            `PQ model metrics unavailable: ${error.message}`;
    }
}

// =============================================
// PQ SCREENING FORM
// =============================================

const pqForm =
    document.getElementById("pqForm");

if (pqForm) {
    pqForm.addEventListener("submit", async event => {
        event.preventDefault();

        const button =
            pqForm.querySelector('button[type="submit"]');

        const error =
            document.getElementById("pqError");

        error.textContent = "";

        const payload = {
            feeder_id: getValue("pqFeeder"),

            line_length_km:
                Number(getValue("pqLineLength")),

            line_r1:
                Number(getValue("pqR1")),

            line_x1:
                Number(getValue("pqX1")),

            phase_a_load_kw:
                Number(getValue("pqPhaseA")),

            phase_b_load_kw:
                Number(getValue("pqPhaseB")),

            phase_c_load_kw:
                Number(getValue("pqPhaseC"))
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
        button.textContent =
            "Running PQ screening...";

        try {
            const data = await postJSON(
                API.pq,
                payload
            );

            displayPQResults(data);

        } catch (err) {
            error.textContent = err.message;

        } finally {
            button.disabled = false;
            button.textContent =
                "Run PQ Screening";
        }
    });
}

// =============================================
// DISPLAY PQ SCREENING RESULTS
// =============================================

function displayPQResults(result) {
    document
        .getElementById("pqResult")
        .classList.remove("hidden");

    setText(
        "pqStatus",
        (result.screening_status || "Unavailable")
            .replaceAll("_", " ")
    );

    setText(
        "pqMessage",
        result.message
    );

    setText(
        "pqClass",
        `${result.predicted_class} — ${result.class_label || "Unknown"}`
    );

    setText(
        "pqScore",
        `${showNumber(result.class_1_model_score_percent)}%`
    );

    setText(
        "pqThreshold",
        `${showNumber(result.screening_threshold_percent)}% VUF`
    );

    setText(
        "pqValidation",
        result.validation_method || "Unavailable"
    );

    fillList(
        "pqLimitations",
        result.limitations
    );

    document
        .getElementById("pqResult")
        .scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
}

// =============================================
// OPENDSS SIMULATION CHARTS
// =============================================

let voltageChartInstance = null;
let transformerChartInstance = null;
let lineChartInstance = null;

async function loadSimulationCharts() {
    const status =
        document.getElementById("chartStatus");

    if (!status) return;

    try {
        if (typeof Chart === "undefined") {
            throw new Error(
                "Chart.js did not load. Check your internet connection."
            );
        }

        const response =
            await fetch(API.hosting);

        const data =
            await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Unable to load simulation results."
            );
        }

        const records =
            data.simulation_results || [];

        const validRecords = records.filter(row =>
            row.result === "PASS" &&
            row.minimum_voltage_pu !== "" &&
            row.maximum_voltage_pu !== "" &&
            row.transformer_loading_percent !== "" &&
            row.line_loading_percent !== ""
        );

        if (!validRecords.length) {
            throw new Error(
                "No valid passing simulation records are available."
            );
        }

        const sorted =
            validRecords.slice().sort(
                (a, b) =>
                    Number(a.solar_kw) -
                    Number(b.solar_kw)
            );

        const solar =
            sorted.map(row => Number(row.solar_kw));

        // COMMON CHART CREATOR

        function createChart(
            canvasId,
            existingInstance,
            datasets,
            yTitle
        ) {
            if (existingInstance) {
                existingInstance.destroy();
            }

            const canvas =
                document.getElementById(canvasId);

            if (!canvas) return null;

            return new Chart(
                canvas,
                {
                    type: "line",

                    data: {
                        labels: solar,
                        datasets: datasets
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
                }
            );
        }

        // VOLTAGE CHART

        voltageChartInstance = createChart(
            "voltageChart",
            voltageChartInstance,
            [
                {
                    label: "Minimum Voltage (pu)",

                    data: sorted.map(
                        row => Number(row.minimum_voltage_pu)
                    ),

                    borderColor: "#34d399",
                    tension: 0.3
                },

                {
                    label: "Maximum Voltage (pu)",

                    data: sorted.map(
                        row => Number(row.maximum_voltage_pu)
                    ),

                    borderColor: "#60a5fa",
                    tension: 0.3
                }
            ],
            "Voltage (pu)"
        );

        // TRANSFORMER CHART

        transformerChartInstance = createChart(
            "transformerChart",
            transformerChartInstance,
            [
                {
                    label: "Transformer Loading (%)",

                    data: sorted.map(
                        row => Number(row.transformer_loading_percent)
                    ),

                    borderColor: "#a78bfa",
                    tension: 0.3
                }
            ],
            "Loading (%)"
        );

        // LINE LOADING CHART

        lineChartInstance = createChart(
            "lineChart",
            lineChartInstance,
            [
                {
                    label: "Distribution Line Loading (%)",

                    data: sorted.map(
                        row => Number(row.line_loading_percent)
                    ),

                    borderColor: "#f59e0b",
                    tension: 0.3
                }
            ],
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
    const status =
        document.getElementById("liveDataStatus");

    if (!status) return;

    status.textContent = "Fetching live data...";

    try {
        const response = await fetch(API.liveData);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Unable to fetch live data."
            );
        }

        const weather = data.weather || {};

        setText(
            "liveTemperature",
            `${showNumber(weather.temperature, 1)} °C`
        );

        setText(
            "liveHumidity",
            `${showNumber(weather.humidity, 0)} %`
        );

        setText(
            "liveCloudCover",
            `${showNumber(weather.cloud_cover, 0)} %`
        );

        setText(
            "liveSolarRadiation",
            `${showNumber(weather.solar_radiation, 1)} W/m²`
        );

        status.textContent =
            `Live data connected · Source: ${data.source}`;

        const updated = data.timestamp
            ? new Date(data.timestamp).toLocaleString("en-IN", {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone: "Asia/Kolkata"
            })
            : "Unavailable";

        setText(
            "liveDataUpdated",
            `Last updated: ${updated}`
        );

    } catch (error) {
        status.textContent =
            `Live data unavailable: ${error.message}`;

        console.error("Live data error:", error);
    }
}

// Refresh live data button

const refreshLiveData =
    document.getElementById("refreshLiveData");

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
    const status =
        document.getElementById("solarForecastStatus");

    const capacityInput =
        document.getElementById("solarCapacity");

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
            throw new Error(
                data.detail || "Unable to generate forecast."
            );
        }

        setText(
            "solarDailyEnergy",
            `${showNumber(data.estimated_total_energy_kwh)} kWh`
        );

        setText(
            "solarInstalledCapacity",
            `${showNumber(data.capacity_kw, 1)} kW`
        );

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

        const canvas =
            document.getElementById("solarForecastChart");

        if (!canvas) return;

        if (solarForecastChart) {
            solarForecastChart.destroy();
        }

        solarForecastChart = new Chart(canvas, {
            type: "line",

            data: {
                labels: labels,

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
                    legend: {
                        display: true
                    }
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

// Forecast button

const solarForecastButton =
    document.getElementById("loadSolarForecast");

if (solarForecastButton) {
    solarForecastButton.addEventListener(
        "click",
        loadSolarForecast
    );
}

// =============================================
// HISTORICAL SOLAR PERFORMANCE ANALYTICS
// =============================================

let monthlySolarChartInstance = null;
let dailySolarChartInstance = null;

async function loadSolarAnalytics() {
    const status =
        document.getElementById("solarAnalyticsStatus");

    const capacityInput =
        document.getElementById("analyticsCapacity");

    const tariffInput =
        document.getElementById("electricityTariff");

    if (!status || !capacityInput || !tariffInput) return;

    const capacity = Number(capacityInput.value);
    const tariff = Number(tariffInput.value);

    if (
        !Number.isFinite(capacity) ||
        capacity <= 0 ||
        !Number.isFinite(tariff) ||
        tariff < 0
    ) {
        status.textContent =
            "Enter valid capacity and electricity tariff.";
        return;
    }

    status.textContent =
        "Loading historical solar analytics...";

    try {
        const response = await fetch(
            `${API.solarAnalytics}?year=2025&capacity_kw=${capacity}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Unable to load solar analytics."
            );
        }

        const monthly = data.monthly_analytics || [];

        if (monthly.length !== 12) {
            throw new Error(
                "Incomplete monthly analytics received."
            );
        }

        const annualEnergy = Number(
            data.estimated_annual_energy_kwh
        );

        const averageMonthly = annualEnergy / 12;

        // SUMMARY CARDS

        setText(
            "analyticsAnnualEnergy",
            `${showNumber(annualEnergy)} kWh`
        );

        setText(
            "analyticsMonthlyEnergy",
            `${showNumber(averageMonthly)} kWh`
        );

        setText(
            "analyticsAnnualSavings",
            `₹ ${showNumber(annualEnergy * tariff, 0)}`
        );

        // FINANCIAL ANALYSIS

        const installationCostInput =
            document.getElementById("solarInstallationCost");

        const installationCost = installationCostInput
            ? Number(installationCostInput.value)
            : NaN;

        if (
            !Number.isFinite(installationCost) ||
            installationCost <= 0
        ) {
            throw new Error(
                "Enter a valid installation cost."
            );
        }

        const annualSavings = annualEnergy * tariff;

        const paybackYears =
            annualSavings > 0
                ? installationCost / annualSavings
                : null;

        const fiveYearBenefit =
            (annualSavings * 5) - installationCost;

        const tenYearBenefit =
            (annualSavings * 10) - installationCost;

        setText(
            "solarPaybackPeriod",
            paybackYears !== null
                ? `${showNumber(paybackYears, 2)} Years`
                : "Unavailable"
        );

        setText(
            "solarFiveYearBenefit",
            `₹ ${showNumber(fiveYearBenefit, 0)}`
        );

        setText(
            "solarTenYearBenefit",
            `₹ ${showNumber(tenYearBenefit, 0)}`
        );

        setText(
            "analyticsInstalledCapacity",
            `${showNumber(data.capacity_kw, 1)} kW`
        );

        const labels = monthly.map(item => item.month);

        const monthlyValues = monthly.map(
            item => Number(item.estimated_energy_kwh)
        );

        const dailyValues = monthly.map(
            item => Number(item.average_daily_energy_kwh)
        );

        // MONTHLY ENERGY CHART

        const monthlyCanvas =
            document.getElementById("monthlySolarChart");

        if (monthlyCanvas) {
            if (monthlySolarChartInstance) {
                monthlySolarChartInstance.destroy();
            }

            monthlySolarChartInstance = new Chart(
                monthlyCanvas,
                {
                    type: "bar",

                    data: {
                        labels: labels,

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
                            legend: {
                                display: true
                            }
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
                }
            );
        }

        // AVERAGE DAILY ENERGY CHART

        const dailyCanvas =
            document.getElementById("dailySolarChart");

        if (dailyCanvas) {
            if (dailySolarChartInstance) {
                dailySolarChartInstance.destroy();
            }

            dailySolarChartInstance = new Chart(
                dailyCanvas,
                {
                    type: "line",

                    data: {
                        labels: labels,

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
                }
            );
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

// GENERATE ANALYTICS BUTTON

const solarAnalyticsButton =
    document.getElementById("loadSolarAnalytics");

if (solarAnalyticsButton) {
    solarAnalyticsButton.addEventListener(
        "click",
        loadSolarAnalytics
    );
}

// =========================================
// ENERGY ADVISOR FRONTEND
// =========================================

async function loadEnergyAdvisor(event) {
    event.preventDefault();

    const errorElement =
        document.getElementById("energyAdvisorError");

    const resultElement =
        document.getElementById("energyAdvisorResult");

    errorElement.textContent = "";
    resultElement.classList.add("hidden");

    const capacity = Number(
        document.getElementById("advisorCapacity").value
    );

    const tariff = Number(
        document.getElementById("advisorTariff").value
    );

    if (
        !Number.isFinite(capacity) ||
        capacity <= 0 ||
        capacity > 1000
    ) {
        errorElement.textContent =
            "Enter a valid solar capacity.";
        return;
    }

    if (
        !Number.isFinite(tariff) ||
        tariff < 0 ||
        tariff > 100
    ) {
        errorElement.textContent =
            "Enter a valid electricity tariff.";
        return;
    }

    const submitButton = document.querySelector(
        "#energyAdvisorForm button[type='submit']"
    );

    submitButton.disabled = true;
    submitButton.textContent = "Generating advice...";

    try {
        const response = await fetch(API.energyAdvisor, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                capacity_kw: capacity,
                electricity_tariff: tariff
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail ||
                "Unable to generate energy advice."
            );
        }

        // SHOW RESULT SECTION

        resultElement.classList.remove("hidden");

        // SUMMARY

        setText(
            "energyAdvisorTitle",
            "Energy Recommendations Generated"
        );

        setText(
            "energyAdvisorSummary",
            `Location: ${data.location} | Advisor: ${data.advisor_type}`
        );

        // MAIN RESULT CARDS

        setText(
            "advisorDailyEnergy",
            `${showNumber(data.estimated_forecast_energy_kwh, 2)} kWh`
        );

        setText(
            "advisorEnergyValue",
            `₹ ${showNumber(data.estimated_energy_value_inr, 2)}`
        );

        setText(
            "advisorCapacityResult",
            `${showNumber(data.installation_capacity_kw, 2)} kW`
        );

        setText(
            "advisorTariffResult",
            `₹ ${showNumber(data.electricity_tariff_inr_per_kwh, 2)} / kWh`
        );

        // HELPER TO DISPLAY LIST ITEMS

        function displayAdvisorList(elementId, items) {
            const list =
                document.getElementById(elementId);

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

        // WEATHER OBSERVATIONS

        displayAdvisorList(
            "advisorWeatherObservations",
            data.weather_observations
        );

        // RECOMMENDATIONS

        displayAdvisorList(
            "advisorRecommendations",
            data.recommendations
        );

        // LIMITATIONS

        displayAdvisorList(
            "advisorLimitations",
            data.limitations
        );

        // CAPACITY COMPARISON

        const comparisonContainer =
            document.getElementById("advisorCapacityComparison");

        if (comparisonContainer) {
            comparisonContainer.replaceChildren();

            if (Array.isArray(data.capacity_comparison)) {
                data.capacity_comparison.forEach(item => {
                    const row = document.createElement("div");
                    row.className = "result-item";

                    const heading = document.createElement("h3");
                    heading.textContent =
                        `${item.capacity_kw} kW System`;

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
        submitButton.textContent =
            "Generate Energy Advice →";
    }
}

// ENERGY ADVISOR FORM LISTENER

const energyAdvisorForm =
    document.getElementById("energyAdvisorForm");

if (energyAdvisorForm) {
    energyAdvisorForm.addEventListener(
        "submit",
        loadEnergyAdvisor
    );
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
        const response = await fetch(
            `${API.solarForecast}?capacity_kw=10`
        );

        if (!response.ok) {
            throw new Error("Solar forecast unavailable");
        }

        const data = await response.json();

        const energy =
            Number(data.estimated_total_energy_kwh);

        setText(
            "intelligenceSolarEnergy",
            `${showNumber(energy, 2)} kWh`
        );

        setText(
            "solarInsight",
            `A 10 kW solar system has an estimated generation of ${showNumber(energy, 2)} kWh over the next 24 hours. This is a weather-based estimate, not measured production.`
        );

    } catch (error) {
        setText("intelligenceSolarEnergy", "Unavailable");

        setText(
            "solarInsight",
            "Solar forecast is currently unavailable. Check the weather service."
        );
    }

    // 2. HOSTING CAPACITY INSIGHT

    try {
        const response = await fetch(API.hosting);

        if (response.status === 404) {
            setText("intelligenceHostingStatus", "NO DATA");

            setText(
                "hostingInsight",
                "No hosting simulation records are currently available. Run an engineering assessment first."
            );

        } else if (!response.ok) {
            throw new Error("Hosting results unavailable");

        } else {
            const data = await response.json();
            const count = Number(data.total_records || 0);

            setText(
                "intelligenceHostingStatus",
                count > 0 ? "AVAILABLE" : "NO DATA"
            );

            setText(
                "hostingInsight",
                count > 0
                    ? `${count} hosting simulation records are available. Review the Engineering Assessment and Analytics pages for feeder-level results.`
                    : "No hosting simulation records are currently available. Run an engineering assessment first."
            );
        }

    } catch (error) {
        setText("intelligenceHostingStatus", "UNAVAILABLE");

        setText(
            "hostingInsight",
            "Hosting results could not be retrieved from the backend."
        );
    }

    // 3. POWER QUALITY INSIGHT

    try {
        const response = await fetch(API.pqInfo);

        if (!response.ok) {
            throw new Error("PQ model unavailable");
        }

        const data = await response.json();

        setText("intelligencePQStatus", "READY");

        setText(
            "pqInsight",
            `The power-quality screening model is available. Model type: ${data.model_type || "PQ screening classifier"}. Run PQ Screening to evaluate a feeder configuration.`
        );

    } catch (error) {
        setText("intelligencePQStatus", "OFFLINE");

        setText(
            "pqInsight",
            "The PQ screening model is unavailable. Check model availability before running screening."
        );
    }

    // 4. ENERGY ADVISOR INSIGHT

    try {
        const response = await fetch(API.energyAdvisor, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                capacity_kw: 10,
                electricity_tariff: 8
            })
        });

        if (!response.ok) {
            throw new Error("Energy Advisor unavailable");
        }

        const data = await response.json();

        setText("intelligenceEnergyStatus", "READY");

        const firstRecommendation =
            Array.isArray(data.recommendations) &&
            data.recommendations.length > 0
                ? data.recommendations[0]
                : "No recommendations available.";

        setText(
            "energyInsight",
            firstRecommendation
        );

    } catch (error) {
        setText("intelligenceEnergyStatus", "OFFLINE");

        setText(
            "energyInsight",
            "Energy Advisor is currently unavailable. Check the weather and solar forecast services."
        );
    }

    // 5. RECENT ASSESSMENT ACTIVITY

    await loadIntelligenceActivity();
}

// =========================================
// RECENT ASSESSMENT ACTIVITY
// =========================================

async function loadIntelligenceActivity() {
    const status =
        document.getElementById("intelligenceActivityStatus");

    const container =
        document.getElementById("intelligenceActivityList");

    if (!status || !container) return;

    try {
        const response = await fetch(
            `${API_BASE}/assessment-history?skip=0&limit=5`
        );

        if (!response.ok) {
            throw new Error("Assessment history unavailable");
        }

        const data = await response.json();

        container.replaceChildren();

        const records = data.assessments || [];

        if (records.length === 0) {
            status.textContent = "No saved assessments yet.";
            return;
        }

        status.textContent =
            `${data.total_records} total saved assessments`;

        records.forEach(record => {
            const item = document.createElement("div");
            item.className = "result-item";

            const heading = document.createElement("h3");

            heading.textContent =
                record.assessment_type || "Assessment";

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
        status.textContent =
            "Unable to load assessment history.";

        container.replaceChildren();
    }
}

// =========================================
// REFRESH PROJECT INTELLIGENCE
// =========================================

const intelligenceRefresh =
    document.getElementById("refreshIntelligence");

if (intelligenceRefresh) {
    intelligenceRefresh.addEventListener(
        "click",
        async () => {
            intelligenceRefresh.disabled = true;
            intelligenceRefresh.textContent = "Refreshing...";

            try {
                await loadProjectIntelligence();
            } finally {
                intelligenceRefresh.disabled = false;
                intelligenceRefresh.textContent =
                    "↻ Refresh Intelligence";
            }
        }
    );
}

// =========================================
// UNIFIED SOLAR PERFORMANCE ANALYTICS
// =========================================

async function loadUnifiedSolarPerformance() {
    const status =
        document.getElementById("unifiedSolarStatus");

    const annualElement =
        document.getElementById("unifiedAnnualEnergy");

    const averageElement =
        document.getElementById("unifiedMonthlyAverage");

    if (!status || !annualElement || !averageElement) {
        return;
    }

    status.textContent =
        "Loading historical solar analytics...";

    try {
        const response = await fetch(
            `${API.solarAnalytics}?year=2025&capacity_kw=10`
        );

        if (!response.ok) {
            throw new Error(
                "Historical solar analytics unavailable."
            );
        }

        const data = await response.json();

        const annualEnergy =
            Number(data.estimated_annual_energy_kwh);

        const monthlyData =
            data.monthly_analytics;

        if (
            !Number.isFinite(annualEnergy) ||
            !Array.isArray(monthlyData) ||
            monthlyData.length !== 12
        ) {
            throw new Error(
                "Invalid historical solar analytics data."
            );
        }

        const monthlyLabels = monthlyData.map(
            item => item.month
        );

        const monthlyEnergy = monthlyData.map(
            item => Number(item.estimated_energy_kwh)
        );

        if (!monthlyEnergy.every(Number.isFinite)) {
            throw new Error(
                "Invalid monthly generation values."
            );
        }

        // ANNUAL GENERATION

        setText(
            "unifiedAnnualEnergy",
            `${showNumber(annualEnergy, 2)} kWh`
        );

        // AVERAGE MONTHLY GENERATION

        setText(
            "unifiedMonthlyAverage",
            `${showNumber(annualEnergy / 12, 2)} kWh`
        );

        // CREATE MONTHLY CHART

        const canvas =
            document.getElementById("unifiedSolarChart");

        if (!canvas) return;

        if (
            window.unifiedSolarChart instanceof Chart
        ) {
            window.unifiedSolarChart.destroy();
        }

        window.unifiedSolarChart = new Chart(
            canvas.getContext("2d"),
            {
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
                        legend: {
                            display: true
                        }
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
            }
        );

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
    const status =
        document.getElementById("reportStatus");

    const container =
        document.getElementById("unifiedReportList");

    if (!status || !container) return;

    status.textContent =
        "Loading assessment records...";

    try {
        const response = await fetch(
            `${API_BASE}/assessment-history?skip=0&limit=10`
        );

        if (!response.ok) {
            throw new Error(
                "Unable to retrieve assessment history."
            );
        }

        const data = await response.json();
        const records = data.assessments || [];

        setText(
            "reportTotalAssessments",
            data.total_records ?? 0
        );

        container.replaceChildren();

        if (records.length === 0) {
            setText("reportLatestType", "None");
            setText("reportLatestDate", "No saved records");

            status.textContent =
                "No assessment records found.";

            return;
        }

        const latest = records[0];

        setText(
            "reportLatestType",
            latest.assessment_type || "Assessment"
        );

        setText(
            "reportLatestDate",
            latest.created_at
                ? new Date(latest.created_at).toLocaleString()
                : "Date unavailable"
        );

        records.forEach(record => {
            const card =
                document.createElement("article");

            card.className = "result-item";

            const heading =
                document.createElement("h3");

            heading.textContent =
                record.assessment_type || "Assessment";

            const feeder =
                document.createElement("p");

            feeder.textContent =
                `Feeder: ${record.feeder_code || "N/A"}`;

            const recordStatus =
                document.createElement("p");

            recordStatus.textContent =
                `Status: ${record.status || "N/A"}`;

            const date =
                document.createElement("p");

            date.textContent = record.created_at
                ? new Date(record.created_at).toLocaleString()
                : "Date unavailable";

            const details =
                document.createElement("button");

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

            card.append(
                heading,
                feeder,
                recordStatus,
                date,
                details
            );

            container.appendChild(card);
        });

        status.textContent =
            `Showing ${records.length} recent records.`;

    } catch (error) {
        status.textContent = error.message;
        container.replaceChildren();
    }
}

// REFRESH REPORT BUTTON

const reportRefreshButton =
    document.getElementById("refreshReport");

if (reportRefreshButton) {
    reportRefreshButton.addEventListener(
        "click",
        async () => {
            reportRefreshButton.disabled = true;
            reportRefreshButton.textContent = "Refreshing...";

            try {
                await loadUnifiedReport();
            } finally {
                reportRefreshButton.disabled = false;
                reportRefreshButton.textContent =
                    "↻ Refresh Report";
            }
        }
    );
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
            throw new Error(
                "Unable to export assessment records."
            );
        }

        const data = await response.json();
        const records = data.assessments || [];

        if (records.length === 0) {
            alert(
                "No assessment records available to export."
            );
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

        const csvContent = [
            headers,
            ...rows
        ].map(row =>
            row.map(escapeCSV).join(",")
        ).join("\n");

        const blob = new Blob(
            ["\uFEFF" + csvContent],
            {
                type: "text/csv;charset=utf-8;"
            }
        );

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download =
            "GridSense_Assessment_Report.csv";

        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(url);

    } catch (error) {
        alert(error.message);
    }
}

// EXPORT BUTTON LISTENER

const exportReportButton =
    document.getElementById("exportReportCSV");

if (exportReportButton) {
    exportReportButton.addEventListener(
        "click",
        exportAssessmentReportCSV
    );
}

// =========================================
// REFRESH OVERVIEW DASHBOARD
// =========================================

async function refreshOverviewDashboard() {
    const button =
        document.getElementById("refreshOverview");

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

// REFRESH OVERVIEW BUTTON

const refreshOverviewButton =
    document.getElementById("refreshOverview");

if (refreshOverviewButton) {
    refreshOverviewButton.addEventListener(
        "click",
        refreshOverviewDashboard
    );
}

// =========================================
// OVERVIEW LAST UPDATED TIMESTAMP
// =========================================

function updateOverviewTimestamp() {
    const timestamp =
        document.getElementById("overviewLastUpdated");

    if (!timestamp) return;

    const now = new Date();

    timestamp.textContent =
        "Last updated: " + now.toLocaleString();
}

// =========================================
// INITIALIZE DASHBOARD
// =========================================

async function initializeDashboard() {
    const isOverviewPage =
        document.getElementById("overviewLastUpdated") ||
        document.getElementById("unifiedReportList") ||
        document.getElementById("intelligenceSolarEnergy");

    // script.js is shared by multiple pages.
    // Only initialize the full dashboard on the Overview page.

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

// START THE OVERVIEW DASHBOARD

initializeDashboard();

// =============================================
// AUTOMATIC LIVE DATA REFRESH — EVERY 5 MINUTES
// =============================================

const LIVE_REFRESH_INTERVAL = 5 * 60 * 1000;

if (document.getElementById("liveDataStatus")) {
    setInterval(() => {
        if (!document.hidden) {
            loadLiveData();
        }
    }, LIVE_REFRESH_INTERVAL);

    // Refresh when returning to the dashboard.

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            loadLiveData();
        }
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


// INITIALIZE ANALYTICS PAGE
if (document.getElementById("chartStatus")) {
    loadSimulationCharts();
}
