// Dryer-specific JavaScript functionality
class DryerController {
  constructor() {
    this.systemType = "dryer";
    this.temperatureChart = null;
    this.datepickerInstance = null;
    this.deviceIds = ["dryer1", "dryer2", "dryer3"];
    this.chartColors = [
      {
        border: "rgba(255, 99, 132, 1)",
        background: "rgba(255, 99, 132, 0.2)",
      },
      {
        border: "rgba(54, 162, 235, 1)",
        background: "rgba(54, 162, 235, 0.2)",
      },
      {
        border: "rgba(75, 192, 192, 1)",
        background: "rgba(75, 192, 192, 0.2)",
      },
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
      console.error("Dryer stream connection error:", err);
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
        noDataMessage.textContent = `Tidak ada data tercatat pada tanggal ${selectedDateStr}.`;
      } else {
        dataSection.style.display = "block";
        tableCaption.textContent = `Menampilkan ${data.length} data untuk ${selectedDateStr}`;

        data.forEach((rowData) => {
          const tr = document.createElement("tr");
          const dryer1 =
            rowData.dryer1 !== null ? `${rowData.dryer1.toFixed(1)}°C` : "N/A";
          const dryer2 =
            rowData.dryer2 !== null ? `${rowData.dryer2.toFixed(1)}°C` : "N/A";
          const dryer3 =
            rowData.dryer3 !== null ? `${rowData.dryer3.toFixed(1)}°C` : "N/A";
          tr.innerHTML = `<td>${rowData.waktu}</td><td>${dryer1}</td><td>${dryer2}</td><td>${dryer3}</td>`;
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
      console.error("Gagal merender chart:", error);
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

// Initialize dryer controller when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  const dryerController = new DryerController();
  dryerController.init();
});
