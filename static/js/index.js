// utils.js - Utility functions untuk aplikasi
const CommonUtils = {
  // Fungsi untuk inisialisasi Flatpickr
  initializeFlatpickr: function (selector, options = {}) {
    const element = document.querySelector(selector);
    if (!element) {
      console.warn("Flatpickr element not found:", selector);
      return null;
    }

    const defaultOptions = {
      dateFormat: "Y-m-d",
      defaultDate: "today",
      maxDate: "today",
    };

    const config = { ...defaultOptions, ...options };

    // Tambahkan tema berdasarkan tema saat ini
    const currentTheme =
      document.documentElement.getAttribute("data-bs-theme") || "dark";
    if (currentTheme === "dark") {
      config.theme = "dark";
    }

    return flatpickr(element, config);
  },

  // Fungsi untuk fetch data dengan error handling
  fetchData: async function (url, params = {}) {
    try {
      const queryString = new URLSearchParams(params).toString();
      const fullUrl = queryString ? `${url}?${queryString}` : url;

      const response = await fetch(fullUrl);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error("Fetch error:", error);
      throw error;
    }
  },

  // Fungsi untuk memformat nilai dengan satuan
  formatValue: function (value, unit = "°C") {
    if (value === null || value === undefined || value === "N/A") {
      return "N/A";
    }

    const numValue = parseFloat(value);
    if (isNaN(numValue)) {
      return "N/A";
    }

    return `${numValue.toFixed(1)}${unit}`;
  },
};

// BaseController - Controller dasar untuk fungsionalitas umum
class BaseController {
  constructor(systemType) {
    this.systemType = systemType;
    this.temperatureChart = null;
    this.datepickerInstance = null;
    this.deviceIds = [];
    this.humidityIds = [];
    this.chartColors = [];
    this.humidityColors = [];
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
    this.datepickerInstance = CommonUtils.initializeFlatpickr("#datePicker", {
      onChange: (selectedDates, dateStr) => {
        this.fetchData(dateStr);
        this.renderChart(
          document.documentElement.getAttribute("data-bs-theme")
        );
      },
    });
  }

  setupDownloadButton() {
    const downloadBtn = document.getElementById("downloadBtn");
    if (downloadBtn) {
      downloadBtn.addEventListener("click", () => {
        if (this.datepickerInstance && this.datepickerInstance.input.value) {
          const selectedDate = this.datepickerInstance.input.value;
          window.open(
            `/download?date=${selectedDate}&type=${this.systemType}`,
            "_blank"
          );
        }
      });
    }
  }

  connectToDataStream() {
    const suhu1Element = document.getElementById("current_suhu_1");
    const suhu2Element = document.getElementById("current_suhu_2");
    const suhu3Element = document.getElementById("current_suhu_3");
    const humidity1Element = document.getElementById("current_humidity_1"); // Elemen humidity

    const eventSource = new EventSource("/stream-data");

    // Definisikan apa yang harus dilakukan ketika pesan diterima
    eventSource.onmessage = function (event) {
      // Parse data JSON yang diterima dari server
      const data = JSON.parse(event.data);

      // Update elemen HTML dengan data baru
      if (suhu1Element) {
        suhu1Element.textContent =
          data.dryer1 !== "N/A" ? `${data.dryer1}°C` : "N/A";
        // Tambahkan class status berdasarkan nilai
        suhu1Element.className = getTemperatureStatusClass(
          parseFloat(data.dryer1)
        );
      }
      if (suhu2Element) {
        suhu2Element.textContent =
          data.dryer2 !== "N/A" ? `${data.dryer2}°C` : "N/A";
        suhu2Element.className = getTemperatureStatusClass(
          parseFloat(data.dryer2)
        );
      }
      if (suhu3Element) {
        suhu3Element.textContent =
          data.dryer3 !== "N/A" ? `${data.dryer3}°C` : "N/A";
        suhu3Element.className = getTemperatureStatusClass(
          parseFloat(data.dryer3)
        );
      }
      if (humidity1Element) {
        humidity1Element.textContent =
          data.humidity1 !== "N/A" ? `${data.humidity1}%` : "N/A";
        // Tambahkan class status berdasarkan nilai humidity
        humidity1Element.className = getHumidityStatusClass(
          parseFloat(data.humidity1)
        );
      }
    };

    // Handle jika terjadi error koneksi
    eventSource.onerror = function (err) {
      console.error("EventSource failed:", err);
      eventSource.close();

      // Coba sambungkan kembali setelah 5 detik
      setTimeout(() => {
        console.log("Attempting to reconnect to data stream...");
        connectToDataStream();
      }, 5000);
    };

    // Fungsi untuk mendapatkan class status humidity
    function getHumidityStatusClass(humidity) {
      if (isNaN(humidity)) return "temp-reading text-secondary";

      if (humidity < 30) {
        return "temp-reading text-warning"; // Low humidity
      } else if (humidity >= 30 && humidity <= 80) {
        return "temp-reading text-primary"; // Normal range
      } else {
        return "temp-reading text-danger"; // High humidity
      }
    }
  }

  // Di dalam KediController
  updateRealTimeDisplay(data) {
    // Update temperature displays
    this.deviceIds.forEach((deviceId) => {
      const element = document.getElementById(`current_${deviceId}`);
      if (element && data[deviceId] !== undefined) {
        element.textContent =
          data[deviceId] !== "N/A" ? `${data[deviceId]}°C` : "N/A";

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
          data[humidityId] !== "N/A" ? `${data[humidityId]}%` : "N/A";

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

  async fetchData(selectedDateStr) {
    if (!selectedDateStr) return;

    const dataSection = document.getElementById("data-section");
    const tableBody = document.getElementById("dataTableBody");
    const loadingIndicator = document.getElementById("loadingIndicator");
    const noDataMessage = document.getElementById("noDataMessage");
    const tableCaption = document.getElementById("tableCaption");

    if (dataSection) dataSection.style.display = "none";
    if (tableBody) tableBody.innerHTML = "";
    if (loadingIndicator) loadingIndicator.style.display = "block";
    if (noDataMessage) noDataMessage.style.display = "none";

    try {
      const data = await CommonUtils.fetchData("/data", {
        date: selectedDateStr,
        type: this.systemType,
      });

      if (loadingIndicator) loadingIndicator.style.display = "none";

      if (!data || data.length === 0) {
        if (noDataMessage) {
          noDataMessage.style.display = "block";
          noDataMessage.textContent = `Tidak ada data ${this.systemType} tercatat pada tanggal ${selectedDateStr}.`;
        }
      } else {
        if (dataSection) dataSection.style.display = "block";
        if (tableCaption) {
          tableCaption.textContent = `Menampilkan ${data.length} data ${this.systemType} untuk ${selectedDateStr}`;
        }

        this.populateDataTable(data, tableBody);
      }
    } catch (error) {
      if (loadingIndicator) loadingIndicator.style.display = "none";
      if (noDataMessage) {
        noDataMessage.textContent = `Error: ${error.message}`;
        noDataMessage.style.display = "block";
      }
      console.error("Fetch error:", error);
    }
  }

  populateDataTable(data, tableBody) {
    // To be implemented by child classes
  }

  async renderChart(theme) {
    try {
      if (!this.datepickerInstance || !this.datepickerInstance.input.value) {
        return;
      }

      const selectedDate = this.datepickerInstance.input.value;
      const chartData = await CommonUtils.fetchData("/chart-data", {
        date: selectedDate,
        type: this.systemType,
      });

      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode
        ? "rgba(255, 255, 255, 0.1)"
        : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      const ctx = document.getElementById("temperatureChart");
      if (!ctx) {
        console.warn("Chart canvas element not found");
        return;
      }

      if (this.temperatureChart) {
        this.temperatureChart.destroy();
      }

      this.temperatureChart = new Chart(ctx.getContext("2d"), {
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

  showNotification(message, type = "info") {
    const toastContainer = document.querySelector(".toast-container");
    if (!toastContainer) {
      console.error("Toast container not found");
      return;
    }

    const toastId = "toast-" + Date.now();
    const toastHtml = `
      <div class="toast" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="toast-header">
          <strong class="me-auto text-${type}">${this.systemType.toUpperCase()} Monitor</strong>
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

// DryerController - Controller khusus untuk sistem dryer
class DryerController extends BaseController {
  constructor() {
    super("dryer");
    this.deviceIds = ["dryer1", "dryer2", "dryer3"];
    this.humidityIds = ["humidity1"];
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
    this.humidityColors = [
      {
        border: "rgba(153, 102, 255, 1)",
        background: "rgba(153, 102, 255, 0.2)",
      },
    ];
  }

  populateDataTable(data, tableBody) {
    if (!tableBody) return;

    data.forEach((rowData) => {
      const tr = document.createElement("tr");
      const dryer1 = CommonUtils.formatValue(rowData.dryer1, "°C");
      const dryer2 = CommonUtils.formatValue(rowData.dryer2, "°C");
      const dryer3 = CommonUtils.formatValue(rowData.dryer3, "°C");
      const humidity1 = CommonUtils.formatValue(rowData.humidity1, "%");

      tr.innerHTML = `
        <td>${rowData.waktu || "N/A"}</td>
        <td>${dryer1}</td>
        <td>${dryer2}</td>
        <td>${dryer3}</td>
      `;
      tableBody.appendChild(tr);
    });
  }
}

// KediController - Controller khusus untuk sistem kedi
class KediController extends BaseController {
  constructor() {
    super("kedi");
    this.deviceIds = ["kedi1", "kedi2", "kedi3", "kedi4"];
    this.humidityIds = ["humidity1"];
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

  populateDataTable(data, tableBody) {
    if (!tableBody) return;

    data.forEach((rowData) => {
      const tr = document.createElement("tr");
      const kedi1 = CommonUtils.formatValue(rowData.kedi1, "°C");
      const kedi2 = CommonUtils.formatValue(rowData.kedi2, "°C");
      const kedi3 = CommonUtils.formatValue(rowData.kedi3, "°C");
      const kedi4 = CommonUtils.formatValue(rowData.kedi4, "°C");
      const humidity4 = CommonUtils.formatValue(rowData.humidity4, "%");

      tr.innerHTML = `
        <td>${rowData.waktu || "N/A"}</td>
        <td>${kedi1}</td>
        <td>${kedi2}</td>
        <td>${kedi3}</td>
      `;
      tableBody.appendChild(tr);
    });
  }

  async renderChart(theme) {
    try {
      const selectedDate = this.datepickerInstance.input.value;
      if (!selectedDate) return;

      const chartData = await CommonUtils.fetchData("/chart-data", {
        date: selectedDate,
        type: this.systemType,
      });

      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode
        ? "rgba(255, 255, 255, 0.1)"
        : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      const ctx = document.getElementById("temperatureChart");
      if (!ctx) {
        console.warn("Chart canvas element not found");
        return;
      }

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

      this.temperatureChart = new Chart(ctx.getContext("2d"), {
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
}

// Fungsi untuk mengelola tema aplikasi
function setupTheme() {
  const themeToggle = document.getElementById("theme-toggle");
  const themeText = document.getElementById("theme-text");
  const htmlElement = document.documentElement;

  const applyTheme = (theme) => {
    htmlElement.setAttribute("data-bs-theme", theme);
    localStorage.setItem("theme", theme);

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

    // Dispatch event untuk memberi tahu controller tentang perubahan tema
    window.dispatchEvent(new CustomEvent("themeChanged", { detail: theme }));
  };

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const newTheme =
        htmlElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      applyTheme(newTheme);
    });
  }

  // Terapkan tema yang disimpan atau default dark
  const savedTheme = localStorage.getItem("theme") || "dark";
  applyTheme(savedTheme);
}

// Fungsi untuk notifikasi toast
function setupNotificationSystem() {
  const notificationSound = new Audio("static/sounds/mixkit-long-pop-2358.wav");

  window.showNotificationToast = function (title, message, level = "info") {
    const toastContainer = document.querySelector(".toast-container");
    if (!toastContainer) {
      console.error("Toast container tidak ditemukan di dalam DOM.");
      return;
    }

    const icons = {
      success:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check-circle-fill text-success me-2" viewBox="0 0 16 16"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg>',
      warning:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-exclamation-triangle-fill text-warning me-2" viewBox="0 0 16 16"><path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/></svg>',
      danger:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-x-octagon-fill text-danger me-2" viewBox="0 0 16 16"><path d="M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353L11.46.146zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708z"/></svg>',
    };

    const icon = icons[level] || "";
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
      delay: 15000,
    });
    toast.show();

    notificationSound.play().catch((error) => {
      console.warn("Pemutaran audio dicegah oleh browser:", error);
    });

    toastElement.addEventListener("hidden.bs.toast", () => {
      toastElement.remove();
    });
  };
}

// Fungsi untuk koneksi notifikasi stream
function connectToNotificationStream() {
  console.log("[SSE] Mencoba terhubung ke /stream-notifications...");
  const eventSource = new EventSource("/stream-notifications");

  eventSource.onopen = function () {
    console.log("[SSE] Koneksi ke stream notifikasi BERHASIL dibuat.");
  };

  eventSource.onmessage = function (event) {
    if (event.data.includes("heartbeat")) {
      console.log("[SSE] Heartbeat diterima dari server.");
      return;
    }

    console.log("[SSE] Data mentah diterima:", event.data);

    try {
      const data = JSON.parse(event.data);
      console.log("[SSE] Data berhasil di-parse:", data);
      if (window.showNotificationToast) {
        window.showNotificationToast(data.title, data.message, data.level);
      }
    } catch (e) {
      console.error("[SSE] Gagal mem-parsing data JSON dari server:", e);
    }
  };

  eventSource.onerror = function (err) {
    console.error("[SSE] Terjadi error pada koneksi EventSource:", err);
    eventSource.close();
    console.log(
      "[SSE] Koneksi ditutup karena error, mencoba lagi dalam 5 detik..."
    );
    setTimeout(connectToNotificationStream, 5000);
  };
}

// Inisialisasi aplikasi ketika DOM sudah dimuat
document.addEventListener("DOMContentLoaded", function () {
  // Setup tema
  setupTheme();

  // Setup sistem notifikasi
  setupNotificationSystem();

  // Koneksi ke stream notifikasi
  connectToNotificationStream();

  // Deteksi sistem yang aktif berdasarkan URL atau atribut HTML
  const isKediSystem =
    window.location.pathname.includes("kedi") ||
    document.body.getAttribute("data-system-type") === "kedi";

  // Inisialisasi controller yang sesuai
  let controller;
  if (isKediSystem) {
    controller = new KediController();
  } else {
    controller = new DryerController();
  }

  // Simpan controller ke window untuk akses global jika diperlukan
  window.appController = controller;

  // Inisialisasi controller
  controller.init();

  console.log(`Sistem ${controller.systemType} diinisialisasi`);
});
