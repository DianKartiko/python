document.addEventListener("DOMContentLoaded", function () {
  // --- Get subdirectory from meta tag or default ---
  const metaSubdir = document.querySelector('meta[name="subdirectory"]');
  const SUBDIRECTORY = metaSubdir ? metaSubdir.content : "/monitoring_website";

  console.log(`Application running in subdirectory: ${SUBDIRECTORY}`);

  // --- Element Initialization ---
  const themeToggle = document.getElementById("theme-toggle");
  const themeText = document.getElementById("theme-text");
  const htmlElement = document.documentElement;
  const dataSection = document.getElementById("data-section");
  const tableBody = document.getElementById("dataTableBody");
  const loadingIndicator = document.getElementById("loadingIndicator");
  const noDataMessage = document.getElementById("noDataMessage");
  const downloadBtn = document.getElementById("downloadBtn");
  const tableCaption = document.getElementById("tableCaption");
  let datepickerInstance = null;

  // --- Configuration ---
  const CONFIG = {
    POLLING_INTERVAL: 60000, // 60 detik (1 menit) sekali polling
    FETCH_TIMEOUT: 30000, // Timeout 30 detik
    MAX_RETRIES: 3,
    RETRY_DELAY: 10000, // Delay 10 detik antara retry
    NOTIFICATION_SOUND_PATH: `${SUBDIRECTORY}/static/sounds/mixkit-long-pop-2358.wav`,
  };

  // --- API Endpoints Configuration --- (DIPERBAIKI)
  const API_ENDPOINTS = {
    currentData: `${SUBDIRECTORY}/current-data`,
    historicalData: `${SUBDIRECTORY}/data`,
    chartData: `${SUBDIRECTORY}/chart-data`,
    humidityData: `${SUBDIRECTORY}/humidity-data`,
    humidityChartData: `${SUBDIRECTORY}/humidity-chart-data`,
    download: `${SUBDIRECTORY}/download`,
  };

  // --- Utility Functions ---
  function showError(message) {
    console.error("Application Error:", message);
    showNotificationToast("Error", message, "danger");
  }

  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  async function fetchWithTimeout(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      CONFIG.FETCH_TIMEOUT
    );

    try {
      console.log(`Fetching: ${url}`);

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          "Cache-Control": "no-cache",
          Pragma: "no-cache",
        },
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }

  // --- Real-time Data Polling dengan Exponential Backoff ---
  let pollingInterval = null;
  let pollingErrors = 0;
  let isPollingActive = true;
  let currentRetryDelay = CONFIG.RETRY_DELAY;

  async function pollData() {
    if (!isPollingActive) return;

    const suhu1Element = document.getElementById("current_suhu_1");
    const suhu2Element = document.getElementById("current_suhu_2");
    const suhu3Element = document.getElementById("current_suhu_3");
    const humidity1Element = document.getElementById("current_humidity_1");
    const mqttStatusElement = document.getElementById("mqtt_status");

    try {
      console.log(
        `[Polling] Attempting to fetch current data (Attempt ${
          pollingErrors + 1
        })`
      );

      const response = await fetchWithTimeout(API_ENDPOINTS.currentData, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      });

      const data = await response.json();
      console.log("Polled real-time data:", data);

      // Reset error counter and retry delay on successful poll
      pollingErrors = 0;
      currentRetryDelay = CONFIG.RETRY_DELAY;

      // Update temperature elements
      if (suhu1Element) {
        suhu1Element.textContent =
          data.dryer1 !== "N/A" ? `${data.dryer1}°C` : "N/A";
      }
      if (suhu2Element) {
        suhu2Element.textContent =
          data.dryer2 !== "N/A" ? `${data.dryer2}°C` : "N/A";
      }
      if (suhu3Element) {
        suhu3Element.textContent =
          data.dryer3 !== "N/A" ? `${data.dryer3}°C` : "N/A";
      }

      // Update humidity elements
      if (humidity1Element) {
        humidity1Element.textContent =
          data.humidity1 !== "N/A" ? `${data.humidity1}%` : "N/A";
      }

      // Update MQTT status indicator
      if (mqttStatusElement) {
        mqttStatusElement.className = data.mqtt_connected
          ? "badge bg-success"
          : "badge bg-warning";
        mqttStatusElement.textContent = data.mqtt_connected
          ? "Connected"
          : "Disconnected";
      }
    } catch (error) {
      pollingErrors++;
      console.error(
        `[Polling] Error ${pollingErrors}/${CONFIG.MAX_RETRIES}:`,
        error
      );

      // Exponential backoff for retries
      currentRetryDelay = Math.min(currentRetryDelay * 2, 60000); // Max 60 seconds

      // Show error only if we've exceeded max errors to avoid spam
      if (pollingErrors >= CONFIG.MAX_RETRIES) {
        showError(
          `Connection issues. Retrying in ${
            currentRetryDelay / 1000
          } seconds...`
        );

        // Stop current interval and restart with backoff
        if (pollingInterval) {
          clearInterval(pollingInterval);
        }

        // Set timeout for retry instead of immediate retry
        setTimeout(() => {
          if (isPollingActive) {
            pollingInterval = setInterval(pollData, CONFIG.POLLING_INTERVAL);
            console.log(`[Polling] Restarted after backoff`);
          }
        }, currentRetryDelay);
      }
    }
  }

  function startDataPolling() {
    console.log(
      `[Polling] Starting with ${CONFIG.POLLING_INTERVAL}ms interval`
    );
    isPollingActive = true;

    // Initial poll
    pollData();

    // Set interval for subsequent polls
    pollingInterval = setInterval(pollData, CONFIG.POLLING_INTERVAL);
  }

  function stopDataPolling() {
    isPollingActive = false;
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
      console.log("[Polling] Stopped");
    }
  }

  // --- Historical Data Functions ---
  async function fetchData(selectedDateStr) {
    if (!selectedDateStr) return;

    dataSection.style.display = "none";
    tableBody.innerHTML = "";
    loadingIndicator.style.display = "block";
    noDataMessage.style.display = "none";

    try {
      const url = `${API_ENDPOINTS.historicalData}?date=${selectedDateStr}&latest_only=false`;
      const response = await fetchWithTimeout(url);

      if (!response.ok) {
        throw new Error(`Failed to fetch data: ${response.statusText}`);
      }

      const data = await response.json();
      loadingIndicator.style.display = "none";

      if (data.length === 0) {
        noDataMessage.style.display = "block";
        noDataMessage.textContent = `No data recorded for ${selectedDateStr}.`;
      } else {
        dataSection.style.display = "block";
        tableCaption.textContent = `Displaying ${data.length} records for ${selectedDateStr}`;

        const fragment = document.createDocumentFragment();

        data.forEach((rowData) => {
          const tr = document.createElement("tr");
          const dryer1 =
            rowData.dryer1 !== null ? `${rowData.dryer1.toFixed(1)}°C` : "N/A";
          const dryer2 =
            rowData.dryer2 !== null ? `${rowData.dryer2.toFixed(1)}°C` : "N/A";
          const dryer3 =
            rowData.dryer3 !== null ? `${rowData.dryer3.toFixed(1)}°C` : "N/A";

          tr.innerHTML = `<td>${rowData.waktu}</td><td>${dryer1}</td><td>${dryer2}</td><td>${dryer3}</td>`;
          fragment.appendChild(tr);
        });

        tableBody.appendChild(fragment);
      }
    } catch (error) {
      loadingIndicator.style.display = "none";
      noDataMessage.textContent = `Error: ${error.message}`;
      noDataMessage.style.display = "block";
      showError(`Failed to load temperature data: ${error.message}`);
    }
  }

  async function fetchHumidityData(selectedDateStr) {
    if (!selectedDateStr) return;

    const humiditySection = document.getElementById("humidity-data-section");
    const humidityTableBody = document.getElementById("humidityDataTableBody");
    const humidityLoadingIndicator = document.getElementById(
      "humidityLoadingIndicator"
    );
    const humidityNoDataMessage = document.getElementById(
      "humidityNoDataMessage"
    );
    const humidityTableCaption = document.getElementById(
      "humidityTableCaption"
    );

    if (!humiditySection) return;

    humiditySection.style.display = "none";
    humidityTableBody.innerHTML = "";
    humidityLoadingIndicator.style.display = "block";
    humidityNoDataMessage.style.display = "none";

    try {
      const url = `${API_ENDPOINTS.humidityData}?date=${selectedDateStr}&sensor_id=humidity1&latest_only=false`;
      const response = await fetchWithTimeout(url);

      if (!response.ok) {
        throw new Error(
          `Failed to fetch humidity data: ${response.statusText}`
        );
      }

      const data = await response.json();
      humidityLoadingIndicator.style.display = "none";

      if (data.length === 0) {
        humidityNoDataMessage.style.display = "block";
        humidityNoDataMessage.textContent = `No humidity data recorded for ${selectedDateStr}.`;
      } else {
        humiditySection.style.display = "block";
        humidityTableCaption.textContent = `Displaying ${data.length} humidity records for ${selectedDateStr}`;

        const fragment = document.createDocumentFragment();

        data.forEach((rowData) => {
          const tr = document.createElement("tr");
          const humidity =
            rowData.humidity !== null
              ? `${rowData.humidity.toFixed(1)}%`
              : "N/A";
          tr.innerHTML = `<td>${rowData.waktu}</td><td>${humidity}</td>`;
          fragment.appendChild(tr);
        });

        humidityTableBody.appendChild(fragment);
      }
    } catch (error) {
      humidityLoadingIndicator.style.display = "none";
      humidityNoDataMessage.textContent = `Error: ${error.message}`;
      humidityNoDataMessage.style.display = "block";
      showError(`Failed to load humidity data: ${error.message}`);
    }
  }

  // --- Theme Functions ---
  function initFlatpickr(theme) {
    if (datepickerInstance) {
      datepickerInstance.destroy();
      datepickerInstance = null;
    }

    let config = {
      dateFormat: "Y-m-d",
      defaultDate: "today",
      maxDate: "today",
      onChange: debounce(function (selectedDates, dateStr) {
        fetchData(dateStr);
        renderChart(htmlElement.getAttribute("data-bs-theme"), dateStr);
        fetchHumidityData(dateStr);
        renderHumidityChart(htmlElement.getAttribute("data-bs-theme"), dateStr);
      }, 300),
    };

    if (theme === "dark") {
      config.theme = "dark";
    }

    try {
      datepickerInstance = flatpickr("#datePicker", config);
    } catch (error) {
      console.error("Failed to initialize datepicker:", error);
    }
  }

  const applyTheme = (theme) => {
    htmlElement.setAttribute("data-bs-theme", theme);

    if (themeText) {
      const themeIconSun = document.getElementById("theme-icon-sun");
      const themeIconMoon = document.getElementById("theme-icon-moon");

      if (theme === "dark") {
        themeText.textContent = "Light Mode";
        if (themeIconSun) themeIconSun.style.display = "inline-block";
        if (themeIconMoon) themeIconMoon.style.display = "none";
      } else {
        themeText.textContent = "Dark Mode";
        if (themeIconSun) themeIconSun.style.display = "none";
        if (themeIconMoon) themeIconMoon.style.display = "inline-block";
      }
    }

    initFlatpickr(theme);

    if (datepickerInstance && datepickerInstance.input.value) {
      const selectedDate = datepickerInstance.input.value;
      renderChart(theme, selectedDate);
      renderHumidityChart(theme, selectedDate);
    }
  };

  // --- Event Listeners ---
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      const newTheme =
        htmlElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      localStorage.setItem("theme", newTheme);
      applyTheme(newTheme);
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener("click", function () {
      if (datepickerInstance && datepickerInstance.input.value) {
        const selectedDate = datepickerInstance.input.value;
        const downloadUrl = `${API_ENDPOINTS.download}?date=${selectedDate}`;
        window.open(downloadUrl, "_blank");
      } else {
        showError("Please select a valid date for download.");
      }
    });
  }

  // --- Chart Variables ---
  let temperatureChart = null;
  let humidityChart = null;

  // --- Temperature Chart Function ---
  async function renderChart(theme, selectedDate) {
    try {
      if (!selectedDate) return;

      const url = `${API_ENDPOINTS.chartData}?date=${selectedDate}`;
      const response = await fetchWithTimeout(url);

      if (!response.ok) {
        throw new Error(`Failed to fetch chart data: ${response.statusText}`);
      }

      const chartData = await response.json();
      const ctx = document.getElementById("temperatureChart");
      if (!ctx) return;

      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode
        ? "rgba(255, 255, 255, 0.1)"
        : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      if (temperatureChart) {
        temperatureChart.destroy();
        temperatureChart = null;
      }

      temperatureChart = new Chart(ctx.getContext("2d"), {
        type: "line",
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: "index",
            intersect: false,
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor },
            },
            y: {
              grid: { color: gridColor },
              ticks: {
                color: textColor,
                callback: function (value) {
                  return value + "°C";
                },
              },
            },
          },
          plugins: {
            legend: {
              labels: { color: textColor },
            },
            title: {
              display: true,
              text: "Temperature Monitoring",
              color: textColor,
            },
          },
        },
      });
    } catch (error) {
      console.error("Failed to render temperature chart:", error);
      showError(`Failed to load temperature chart: ${error.message}`);
    }
  }

  // --- Humidity Chart Function ---
  async function renderHumidityChart(theme, selectedDate) {
    try {
      if (!selectedDate) return;

      const url = `${API_ENDPOINTS.humidityChartData}?date=${selectedDate}`;
      const response = await fetchWithTimeout(url);

      if (!response.ok) {
        throw new Error(
          `Failed to fetch humidity chart data: ${response.statusText}`
        );
      }

      const chartData = await response.json();
      const ctx = document.getElementById("humidityChart");
      if (!ctx) return;

      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode
        ? "rgba(255, 255, 255, 0.1)"
        : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      if (humidityChart) {
        humidityChart.destroy();
        humidityChart = null;
      }

      humidityChart = new Chart(ctx.getContext("2d"), {
        type: "line",
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: "index",
            intersect: false,
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor },
            },
            y: {
              grid: { color: gridColor },
              ticks: {
                color: textColor,
                callback: function (value) {
                  return value + "%";
                },
              },
              min: 0,
              max: 100,
            },
          },
          plugins: {
            legend: {
              labels: { color: textColor },
            },
            title: {
              display: true,
              text: "Humidity Level (%)",
              color: textColor,
            },
          },
        },
      });
    } catch (error) {
      console.error("Failed to render humidity chart:", error);
      showError(`Failed to load humidity chart: ${error.message}`);
    }
  }

  // --- Notification System ---
  let notificationSound = null;

  function initializeNotificationSound() {
    try {
      notificationSound = new Audio(CONFIG.NOTIFICATION_SOUND_PATH);
      notificationSound.preload = "auto";
    } catch (error) {
      console.warn("Failed to initialize notification sound:", error);
    }
  }

  function showNotificationToast(title, message, level = "info") {
    const toastContainer = document.querySelector(".toast-container");
    if (!toastContainer) {
      console.error("Toast container not found in DOM.");
      return;
    }

    const icons = {
      success:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check-circle-fill text-success me-2" viewBox="0 0 16 16"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg>',
      warning:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-exclamation-triangle-fill text-warning me-2" viewBox="0 0 16 16"><path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/></svg>',
      danger:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-x-octagon-fill text-danger me-2" viewBox="0 0 16 16"><path d="M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353L11.46.146zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708z"/></svg>',
      info: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-info-circle-fill text-info me-2" viewBox="0 0 16 16"><path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16zm.93-9.412-1 4.705c-.07.34.029.533.304.533.194 0 .487-.07.686-.246l-.088.416c-.287.346-.92.598-1.465.598-.703 0-1.002-.422-.808-1.319l.738-3.468c.064-.293.006-.399-.287-.47l-.451-.081.082-.381 2.29-.287zM8 5.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2z"/></svg>',
    };

    const icon = icons[level] || icons.info;
    const now = new Date();
    const timeString = `${now.getHours().toString().padStart(2, "0")}:${now
      .getMinutes()
      .toString()
      .padStart(2, "0")}`;

    const toastElement = document.createElement("div");
    toastElement.classList.add("toast");
    toastElement.setAttribute("role", "alert");
    toastElement.setAttribute("aria-live", "assertive");
    toastElement.setAttribute("aria-atomic", "true");

    toastElement.innerHTML = `
      <div class="toast-header">
        ${icon}
        <strong class="me-auto">${title}</strong>
        <small class="text-muted">${timeString}</small>
        <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
      <div class="toast-body">
        ${message}
      </div>
    `;

    toastContainer.appendChild(toastElement);

    const toast = new bootstrap.Toast(toastElement, {
      delay: level === "danger" ? 30000 : 15000,
    });
    toast.show();

    if (notificationSound && (level === "danger" || level === "warning")) {
      notificationSound.play().catch((error) => {
        console.warn("Audio playback blocked by browser:", error);
      });
    }

    toastElement.addEventListener("hidden.bs.toast", () => {
      toastElement.remove();
    });
  }

  // --- Application Lifecycle ---
  function initializeApplication() {
    console.log(
      "Initializing Temperature Monitoring Application (Polling Mode)"
    );

    const savedTheme = localStorage.getItem("theme") || "dark";
    applyTheme(savedTheme);
    initializeNotificationSound();
    startDataPolling();

    setTimeout(() => {
      if (datepickerInstance && datepickerInstance.input) {
        const today = datepickerInstance.input.value;
        fetchData(today);
        fetchHumidityData(today);
      }
    }, 500);

    console.log("Application initialization complete");
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      console.log("Page hidden, stopping polling");
      stopDataPolling();
    } else {
      console.log("Page visible, resuming polling");
      startDataPolling();
    }
  }

  function handleBeforeUnload() {
    stopDataPolling();

    if (temperatureChart) {
      temperatureChart.destroy();
    }
    if (humidityChart) {
      humidityChart.destroy();
    }
  }

  // --- Event Listeners ---
  document.addEventListener("visibilitychange", handleVisibilityChange);
  window.addEventListener("beforeunload", handleBeforeUnload);

  window.addEventListener("error", function (event) {
    console.error("Global error:", event.error);
    showError(
      "An unexpected error occurred. Please refresh the page if issues persist."
    );
  });

  window.addEventListener("unhandledrejection", function (event) {
    console.error("Unhandled promise rejection:", event.reason);
    showError("A network or processing error occurred.");
  });

  // --- Initialize Application ---
  try {
    initializeApplication();
  } catch (error) {
    console.error("Failed to initialize application:", error);
    showError("Failed to initialize the application. Please refresh the page.");
  }

  // Debug functions
  window.temperatureMonitor = {
    restartPolling: function () {
      stopDataPolling();
      startDataPolling();
    },
    getPollingStatus: function () {
      return pollingInterval ? "Running" : "Stopped";
    },
    testNotification: function () {
      showNotificationToast("Test", "This is a test notification", "info");
    },
    getEndpoints: function () {
      return API_ENDPOINTS;
    },
  };
});
