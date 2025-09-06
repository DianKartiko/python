// Kedi-specific JavaScript functionality
class KediController {
  constructor() {
    this.systemType = "kedi";
    this.temperatureChart = null;
    this.datepickerInstance = null;
    this.deviceIds = ["kedi1", "kedi2", "kedi3", "kedi4"];
    this.humidityIds = ["humidity4"]; // Array untuk humidity sensors
    this.chartColors = [
      { border: "rgba(255, 193, 7, 1)", background: "rgba(255, 193, 7, 0.2)" },
      { border: "rgba(220, 53, 69, 1)", background: "rgba(220, 53, 69, 0.2)" },
      {
        border: "rgba(54, 162, 235, 1)",
        background: "rgba(54, 162, 235, 0.2)",
      },
      {
        border: "rgba(153, 102, 255, 1)",
        background: "rgba(153, 102, 255, 0.2)",
      },
    ];
    this.humidityColors = [
      { border: "rgba(40, 167, 69, 1)", background: "rgba(40, 167, 69, 0.2)" },
    ];
  }

  init() {
    this.setupDatePicker();
    this.setupDownloadButton();
    this.connectToDataStream();
    this.loadInitialData();

    // Listen for theme changes
    window.addEventListener("themeChanged", (e) => {
      this.renderChart(e.detail);
    });
  }

  setupDatePicker() {
    this.datepickerInstance = window.commonUtils.initializeFlatpickr(
      "#datePicker",
      {
        onChange: (selectedDates, dateStr) => {
          this.fetchData(dateStr);
          this.renderChart(
            document.documentElement.getAttribute("data-bs-theme")
          );
        },
      }
    );
  }

  setupDownloadButton() {
    const downloadBtn = document.getElementById("downloadBtn");
    if (downloadBtn) {
      downloadBtn.addEventListener("click", () => {
        const selectedDate = this.datepickerInstance.input.value;
        if (selectedDate) {
          window.open(
            `/download?date=${selectedDate}&type=${this.systemType}`,
            "_blank"
          );
        }
      });
    }
  }

  connectToDataStream() {
    const eventSource = new EventSource("/stream-data");

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.updateRealTimeDisplay(data);
    };

    eventSource.onerror = (err) => {
      console.error("Kedi stream connection error:", err);
      eventSource.close();

      // Attempt to reconnect after 5 seconds
      setTimeout(() => {
        console.log("Attempting to reconnect to data stream...");
        this.connectToDataStream();
      }, 5000);
    };
  }

  updateRealTimeDisplay(data) {
    // Update temperature displays
    this.deviceIds.forEach((deviceId) => {
      const element = document.getElementById(`current_${deviceId}`);
      if (element && data[deviceId] !== undefined) {
        element.textContent =
          data[deviceId] !== null && data[deviceId] !== "N/A"
            ? `${parseFloat(data[deviceId]).toFixed(1)}°C`
            : "N/A";

        // Add status indicator based on temperature value
        const tempValue = parseFloat(data[deviceId]);
        if (!isNaN(tempValue)) {
          element.className = this.getTemperatureStatusClass(tempValue);
        }
      }
    });

    // Update humidity displays
    this.humidityIds.forEach((humidityId) => {
      const element = document.getElementById(`current_${humidityId}`);
      if (element && data[humidityId] !== undefined) {
        element.textContent =
          data[humidityId] !== null && data[humidityId] !== "N/A"
            ? `${parseFloat(data[humidityId]).toFixed(1)}%`
            : "N/A";

        // Add status indicator based on humidity value
        const humidityValue = parseFloat(data[humidityId]);
        if (!isNaN(humidityValue)) {
          element.className = this.getHumidityStatusClass(humidityValue);
        }
      }
    });

    // Update timestamp display
    const timestampElement = document.getElementById("lastUpdateTime");
    if (timestampElement) {
      const now = new Date().toLocaleString("id-ID", {
        timeZone: "Asia/Jakarta",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      timestampElement.textContent = now;
    }
  }

  getTemperatureStatusClass(temperature) {
    if (temperature < 120) {
      return "temp-reading text-info"; // Low temperature
    } else if (temperature >= 120 && temperature <= 155) {
      return "temp-reading text-success"; // Normal range
    } else {
      return "temp-reading text-danger"; // High temperature
    }
  }

  getHumidityStatusClass(humidity) {
    if (humidity < 30) {
      return "temp-reading text-warning"; // Low humidity
    } else if (humidity >= 30 && humidity <= 80) {
      return "temp-reading text-success"; // Normal range
    } else {
      return "temp-reading text-danger"; // High humidity
    }
  }

  async fetchData(selectedDateStr) {
    if (!selectedDateStr) return;

    const dataSection = document.getElementById("data-section");
    const tableBody = document.getElementById("dataTableBody");
    const loadingIndicator = document.getElementById("loadingIndicator");
    const noDataMessage = document.getElementById("noDataMessage");
    const tableCaption = document.getElementById("tableCaption");

    dataSection.style.display = "none";
    tableBody.innerHTML = "";
    loadingIndicator.style.display = "block";
    noDataMessage.style.display = "none";

    try {
      const data = await window.commonUtils.fetchData("/data", {
        date: selectedDateStr,
        type: this.systemType,
      });

      loadingIndicator.style.display = "none";

      if (data.length === 0) {
        noDataMessage.style.display = "block";
        noDataMessage.textContent = `Tidak ada data kedi tercatat pada tanggal ${selectedDateStr}.`;
      } else {
        dataSection.style.display = "block";
        tableCaption.textContent = `Menampilkan ${data.length} data kedi untuk ${selectedDateStr}`;

        data.forEach((rowData) => {
          const tr = document.createElement("tr");
          const kedi1 =
            rowData.kedi1 !== null ? `${rowData.kedi1.toFixed(1)}°C` : "N/A";
          const kedi2 =
            rowData.kedi2 !== null ? `${rowData.kedi2.toFixed(1)}°C` : "N/A";
          const kedi3 =
            rowData.kedi3 !== null ? `${rowData.kedi3.toFixed(1)}°C` : "N/A";
          const kedi4 =
            rowData.kedi4 !== null ? `${rowData.kedi4.toFixed(1)}°C` : "N/A";
          const humidity4 =
            rowData.humidity4 !== null
              ? `${rowData.humidity4.toFixed(1)}%`
              : "N/A";

          tr.innerHTML = `
            <td>${rowData.waktu}</td>
            <td>${kedi1}</td>
            <td>${kedi2}</td>
            <td>${kedi3}</td>
            <td>${kedi4}</td>
            <td>${humidity4}</td>
          `;
          tableBody.appendChild(tr);
        });
      }
    } catch (error) {
      loadingIndicator.style.display = "none";
      noDataMessage.textContent = `Error: ${error.message}`;
      noDataMessage.style.display = "block";
      console.error("Fetch error:", error);
    }
  }

  async renderChart(theme) {
    try {
      const selectedDate = this.datepickerInstance.input.value;
      if (!selectedDate) return;

      const chartData = await window.commonUtils.fetchData("/chart-data", {
        date: selectedDate,
        type: this.systemType,
      });

      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode
        ? "rgba(255, 255, 255, 0.1)"
        : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      const ctx = document.getElementById("temperatureChart").getContext("2d");

      if (this.temperatureChart) {
        this.temperatureChart.destroy();
      }

      // Create separate datasets for temperature and humidity
      const datasets = [];

      // Temperature datasets
      if (chartData.datasets) {
        chartData.datasets.forEach((dataset, index) => {
          if (dataset.label.includes("Kedi")) {
            datasets.push({
              ...dataset,
              yAxisID: "temperature",
              borderColor:
                this.chartColors[index % this.chartColors.length].border,
              backgroundColor:
                this.chartColors[index % this.chartColors.length].background,
            });
          }
        });
      }

      // Humidity dataset (if available in chart data)
      if (chartData.datasets) {
        chartData.datasets.forEach((dataset) => {
          if (dataset.label.includes("Humidity")) {
            datasets.push({
              ...dataset,
              yAxisID: "humidity",
              borderColor: this.humidityColors[0].border,
              backgroundColor: this.humidityColors[0].background,
            });
          }
        });
      }

      this.temperatureChart = new Chart(ctx, {
        type: "line",
        data: {
          ...chartData,
          datasets: datasets,
        },
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
            temperature: {
              type: "linear",
              display: true,
              position: "left",
              grid: { color: gridColor },
              ticks: {
                color: textColor,
                callback: function (value) {
                  return value + "°C";
                },
              },
              title: {
                display: true,
                text: "Temperature (°C)",
                color: textColor,
              },
            },
            humidity: {
              type: "linear",
              display: true,
              position: "right",
              grid: { drawOnChartArea: false },
              ticks: {
                color: textColor,
                callback: function (value) {
                  return value + "%";
                },
              },
              title: {
                display: true,
                text: "Humidity (%)",
                color: textColor,
              },
            },
          },
          plugins: {
            legend: {
              labels: { color: textColor },
            },
            tooltip: {
              callbacks: {
                label: function (context) {
                  let label = context.dataset.label || "";
                  if (label) {
                    label += ": ";
                  }
                  if (context.dataset.yAxisID === "humidity") {
                    label += context.parsed.y + "%";
                  } else {
                    label += context.parsed.y + "°C";
                  }
                  return label;
                },
              },
            },
          },
        },
      });
    } catch (error) {
      console.error("Gagal merender chart kedi:", error);
    }
  }

  loadInitialData() {
    setTimeout(() => {
      if (this.datepickerInstance && this.datepickerInstance.input) {
        const today = this.datepickerInstance.input.value;
        this.fetchData(today);
      }
    }, 100);
  }

  // Method untuk menampilkan notifikasi toast
  showNotification(message, type = "info") {
    const toastContainer = document.querySelector(".toast-container");
    const toastId = "toast-" + Date.now();

    const toastHtml = `
      <div class="toast" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="toast-header">
          <strong class="me-auto text-${type}">Kedi Monitor</strong>
          <small>sekarang</small>
          <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
          ${message}
        </div>
      </div>
    `;

    toastContainer.innerHTML += toastHtml;

    const toast = new bootstrap.Toast(document.getElementById(toastId));
    toast.show();

    // Auto remove toast after it's hidden
    document.getElementById(toastId).addEventListener("hidden.bs.toast", () => {
      document.getElementById(toastId).remove();
    });
  }
}

// Initialize kedi controller when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  const kediController = new KediController();
  kediController.init();
});
