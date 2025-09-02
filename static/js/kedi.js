// Kedi-specific JavaScript functionality
class KediController {
  constructor() {
    this.systemType = "kedi";
    this.temperatureChart = null;
    this.datepickerInstance = null;
    this.deviceIds = ["kedi1", "kedi2"];
    this.chartColors = [
      { border: "rgba(255, 193, 7, 1)", background: "rgba(255, 193, 7, 0.2)" },
      { border: "rgba(220, 53, 69, 1)", background: "rgba(220, 53, 69, 0.2)" },
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
    };
  }

  updateRealTimeDisplay(data) {
    this.deviceIds.forEach((deviceId) => {
      const element = document.getElementById(`current_${deviceId}`);
      if (element && data[deviceId]) {
        element.textContent =
          data[deviceId] !== "N/A" ? `${data[deviceId]}°C` : "N/A";
      }
    });
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
          tr.innerHTML = `<td>${rowData.waktu}</td><td>${kedi1}</td><td>${kedi2}</td>`;
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

      this.temperatureChart = new Chart(ctx, {
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
}

// Initialize kedi controller when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  const kediController = new KediController();
  kediController.init();
});
