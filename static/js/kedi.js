// Enhanced Kedi Controller dengan dual sensor support
class KediController {
  constructor() {
    this.systemType = "kedi";
    this.temperatureChart = null;
    this.humidityChart = null;
    this.datepickerInstance = null;
    this.deviceIds = ["kedi1", "kedi2", "kedi3", "kedi4"];  // UPDATE untuk 4 kedi
    this.currentDataType = "temperature";
    this.chartColors = {
      temperature: [
        { border: "rgba(220, 53, 69, 1)", background: "rgba(220, 53, 69, 0.2)" },
        { border: "rgba(255, 193, 7, 1)", background: "rgba(255, 193, 7, 0.2)" },
        { border: "rgba(40, 167, 69, 1)", background: "rgba(40, 167, 69, 0.2)" },
        { border: "rgba(23, 162, 184, 1)", background: "rgba(23, 162, 184, 0.2)" }
      ],
      humidity: [
        { border: "rgba(102, 16, 242, 1)", background: "rgba(102, 16, 242, 0.2)" },
        { border: "rgba(253, 126, 20, 1)", background: "rgba(253, 126, 20, 0.2)" },
        { border: "rgba(32, 201, 151, 1)", background: "rgba(32, 201, 151, 0.2)" },
        { border: "rgba(232, 62, 140, 1)", background: "rgba(232, 62, 140, 0.2)" }
      ]
    };
  }

  init() {
    this.setupDatePicker();
    this.setupDataTypeSelector();  // TAMBAHAN
    this.setupDownloadButton();
    this.connectToDataStream();
    this.loadInitialData();

    // Listen for theme changes
    window.addEventListener("themeChanged", (e) => {
      this.renderChart(e.detail);
    });
  }

  setupDatePicker() {
    this.datepickerInstance = window.commonUtils.initializeFlatpickr("#datePicker", {
      onChange: (selectedDates, dateStr) => {
        this.fetchData(dateStr);
        this.renderChart(document.documentElement.getAttribute("data-bs-theme"));
      },
    });
  }

  // TAMBAHAN: Setup data type selector
  setupDataTypeSelector() {
    const selector = document.getElementById("dataTypeSelector");
    if (selector) {
      selector.addEventListener("change", (e) => {
        this.currentDataType = e.target.value;
        const selectedDate = this.datepickerInstance.input.value;
        if (selectedDate) {
          this.fetchData(selectedDate);
          this.renderChart(document.documentElement.getAttribute("data-bs-theme"));
        }
      });
    }
  }

  setupDownloadButton() {
    const downloadBtn = document.getElementById("downloadBtn");
    if (downloadBtn) {
      downloadBtn.addEventListener("click", () => {
        const selectedDate = this.datepickerInstance.input.value;
        const dataType = this.currentDataType;
        if (selectedDate) {
          let downloadUrl;
          if (dataType === "both") {
            // Download kombinasi temperature dan humidity
            downloadUrl = `/download-combined?date=${selectedDate}&type=kedi`;
          } else {
            downloadUrl = `/download?date=${selectedDate}&type=${this.systemType}&sensor=${dataType}`;
          }
          window.open(downloadUrl, "_blank");
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
    // Update temperature displays
    this.deviceIds.forEach((deviceId) => {
      const tempElement = document.getElementById(`current_${deviceId}`);
      if (tempElement && data[deviceId]) {
        tempElement.textContent = data[deviceId] !== "N/A" ? `${data[deviceId]}°C` : "N/A";
      }

      // TAMBAHAN: Update humidity displays
      const humidityElement = document.getElementById(`current_${deviceId}_humidity`);
      if (humidityElement && data[`${deviceId}_humidity`]) {
        humidityElement.textContent = 
          data[`${deviceId}_humidity`] !== "N/A" ? `${data[`${deviceId}_humidity`]}%` : "N/A";
      }
    });
  }

  async fetchData(selectedDateStr) {
    if (!selectedDateStr) return;

    const dataSection = document.getElementById("data-section");
    const tableBody = document.getElementById("dataTableBody");
    const tableHeaders = document.getElementById("tableHeaders");
    const loadingIndicator = document.getElementById("loadingIndicator");
    const noDataMessage = document.getElementById("noDataMessage");
    const tableCaption = document.getElementById("tableCaption");

    dataSection.style.display = "none";
    tableBody.innerHTML = "";
    loadingIndicator.style.display = "block";
    noDataMessage.style.display = "none";

    try {
      let data;
      let endpoint;
      
      // TAMBAHAN: Determine endpoint based on data type
      switch (this.currentDataType) {
        case "temperature":
          endpoint = "/data";
          data = await window.commonUtils.fetchData(endpoint, {
            date: selectedDateStr,
            type: this.systemType,
          });
          this.setupTemperatureTable(tableHeaders, data, selectedDateStr, tableCaption, tableBody);
          break;
          
        case "humidity":
          endpoint = "/humidity-data";
          data = await window.commonUtils.fetchData(endpoint, {
            date: selectedDateStr,
            type: this.systemType,
          });
          this.setupHumidityTable(tableHeaders, data, selectedDateStr, tableCaption, tableBody);
          break;
          
        case "both":
          // Fetch both temperature and humidity data
          const [tempData, humidityData] = await Promise.all([
            window.commonUtils.fetchData("/data", { date: selectedDateStr, type: this.systemType }),
            window.commonUtils.fetchData("/humidity-data", { date: selectedDateStr, type: this.systemType })
          ]);
          this.setupCombinedTable(tableHeaders, tempData, humidityData, selectedDateStr, tableCaption, tableBody);
          data = tempData; // For length check
          break;
      }

      loadingIndicator.style.display = "none";

      if (data && data.length === 0) {
        noDataMessage.style.display = "block";
        noDataMessage.textContent = `Tidak ada data ${this.currentDataType} tercatat pada tanggal ${selectedDateStr}.`;
      } else {
        dataSection.style.display = "block";
      }
    } catch (error) {
      loadingIndicator.style.display = "none";
      noDataMessage.textContent = `Error: ${error.message}`;
      noDataMessage.style.display = "block";
      console.error("Fetch error:", error);
    }
  }

  // TAMBAHAN: Setup temperature table
  setupTemperatureTable(tableHeaders, data, selectedDate, tableCaption, tableBody) {
    // Setup headers for temperature
    tableHeaders.innerHTML = `
      <th>Waktu (WIB)</th>
      <th>Kedi 1 (°C)</th>
      <th>Kedi 2 (°C)</th>
      <th>Kedi 3 (°C)</th>
      <th>Kedi 4 (°C)</th>
    `;

    tableCaption.textContent = `Menampilkan ${data.length} data suhu untuk ${selectedDate}`;

    data.forEach((rowData) => {
      const tr = document.createElement("tr");
      const kedi1 = rowData.kedi1 !== null ? `${rowData.kedi1.toFixed(1)}°C` : "N/A";
      const kedi2 = rowData.kedi2 !== null ? `${rowData.kedi2.toFixed(1)}°C` : "N/A";
      const kedi3 = rowData.kedi3 !== null ? `${rowData.kedi3.toFixed(1)}°C` : "N/A";
      const kedi4 = rowData.kedi4 !== null ? `${rowData.kedi4.toFixed(1)}°C` : "N/A";
      tr.innerHTML = `<td>${rowData.waktu}</td><td>${kedi1}</td><td>${kedi2}</td><td>${kedi3}</td><td>${kedi4}</td>`;
      tableBody.appendChild(tr);
    });
  }

  // TAMBAHAN: Setup humidity table
  setupHumidityTable(tableHeaders, data, selectedDate, tableCaption, tableBody) {
    // Setup headers for humidity
    tableHeaders.innerHTML = `
      <th>Waktu (WIB)</th>
      <th>Kedi 1 (%)</th>
      <th>Kedi 2 (%)</th>
      <th>Kedi 3 (%)</th>
      <th>Kedi 4 (%)</th>
    `;

    tableCaption.textContent = `Menampilkan ${data.length} data kelembaban untuk ${selectedDate}`;

    data.forEach((rowData) => {
      const tr = document.createElement("tr");
      const kedi1_h = rowData.kedi1_humidity !== null ? `${rowData.kedi1_humidity.toFixed(1)}%` : "N/A";
      const kedi2_h = rowData.kedi2_humidity !== null ? `${rowData.kedi2_humidity.toFixed(1)}%` : "N/A";
      const kedi3_h = rowData.kedi3_humidity !== null ? `${rowData.kedi3_humidity.toFixed(1)}%` : "N/A";
      const kedi4_h = rowData.kedi4_humidity !== null ? `${rowData.kedi4_humidity.toFixed(1)}%` : "N/A";
      tr.innerHTML = `<td>${rowData.waktu}</td><td>${kedi1_h}</td><td>${kedi2_h}</td><td>${kedi3_h}</td><td>${kedi4_h}</td>`;
      tableBody.appendChild(tr);
    });
  }

  // TAMBAHAN: Setup combined table
  setupCombinedTable(tableHeaders, tempData, humidityData, selectedDate, tableCaption, tableBody) {
    // Setup headers for combined data
    tableHeaders.innerHTML = `
      <th>Waktu (WIB)</th>
      <th>K1 Suhu</th>
      <th>K1 Lembab</th>
      <th>K2 Suhu</th>
      <th>K2 Lembab</th>
      <th>K3 Suhu</th>
      <th>K3 Lembab</th>
      <th>K4 Suhu</th>
      <th>K4 Lembab</th>
    `;

    tableCaption.textContent = `Menampilkan ${Math.max(tempData.length, humidityData.length)} data kombinasi untuk ${selectedDate}`;

    // Merge data by timestamp
    const mergedData = this.mergeDataByTimestamp(tempData, humidityData);

    mergedData.forEach((rowData) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${rowData.waktu}</td>
        <td>${rowData.kedi1_temp !== null ? `${rowData.kedi1_temp.toFixed(1)}°C` : "N/A"}</td>
        <td>${rowData.kedi1_humidity !== null ? `${rowData.kedi1_humidity.toFixed(1)}%` : "N/A"}</td>
        <td>${rowData.kedi2_temp !== null ? `${rowData.kedi2_temp.toFixed(1)}°C` : "N/A"}</td>
        <td>${rowData.kedi2_humidity !== null ? `${rowData.kedi2_humidity.toFixed(1)}%` : "N/A"}</td>
        <td>${rowData.kedi3_temp !== null ? `${rowData.kedi3_temp.toFixed(1)}°C` : "N/A"}</td>
        <td>${rowData.kedi3_humidity !== null ? `${rowData.kedi3_humidity.toFixed(1)}%` : "N/A"}</td>
        <td>${rowData.kedi4_temp !== null ? `${rowData.kedi4_temp.toFixed(1)}°C` : "N/A"}</td>
        <td>${rowData.kedi4_humidity !== null ? `${rowData.kedi4_humidity.toFixed(1)}%` : "N/A"}</td>
      `;
      tableBody.appendChild(tr);
    });
  }

  // TAMBAHAN: Merge data by timestamp
  mergeDataByTimestamp(tempData, humidityData) {
    const mergedMap = new Map();
    
    // Add temperature data
    tempData.forEach(item => {
      mergedMap.set(item.waktu, {
        waktu: item.waktu,
        kedi1_temp: item.kedi1,
        kedi2_temp: item.kedi2,
        kedi3_temp: item.kedi3,
        kedi4_temp: item.kedi4,
        kedi1_humidity: null,
        kedi2_humidity: null,
        kedi3_humidity: null,
        kedi4_humidity: null
      });
    });
    
    // Add humidity data
    humidityData.forEach(item => {
      if (mergedMap.has(item.waktu)) {
        const existing = mergedMap.get(item.waktu);
        existing.kedi1_humidity = item.kedi1_humidity;
        existing.kedi2_humidity = item.kedi2_humidity;
        existing.kedi3_humidity = item.kedi3_humidity;
        existing.kedi4_humidity = item.kedi4_humidity;
      } else {
        mergedMap.set(item.waktu, {
          waktu: item.waktu,
          kedi1_temp: null,
          kedi2_temp: null,
          kedi3_temp: null,
          kedi4_temp: null,
          kedi1_humidity: item.kedi1_humidity,
          kedi2_humidity: item.kedi2_humidity,
          kedi3_humidity: item.kedi3_humidity,
          kedi4_humidity: item.kedi4_humidity
        });
      }
    });
    
    return Array.from(mergedMap.values()).sort((a, b) => a.waktu.localeCompare(b.waktu));
  }

  async renderChart(theme) {
    try {
      const selectedDate = this.datepickerInstance.input.value;
      if (!selectedDate) return;

      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      if (this.currentDataType === "temperature" || this.currentDataType === "both") {
        await this.renderTemperatureChart(selectedDate, gridColor, textColor);
      }
      
      if (this.currentDataType === "humidity" || this.currentDataType === "both") {
        await this.renderHumidityChart(selectedDate, gridColor, textColor);
      }
    } catch (error) {
      console.error("Gagal merender chart:", error);
    }
  }

  async renderTemperatureChart(selectedDate, gridColor, textColor) {
    const chartData = await window.commonUtils.fetchData("/chart-data", {
      date: selectedDate,
      type: this.systemType,
    });

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
        interaction: { mode: "index", intersect: false },
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
          legend: { labels: { color: textColor } },
          title: {
            display: true,
            text: 'Grafik Suhu Harian (MAX6675)',
            color: textColor
          }
        },
      },
    });
  }

  async renderHumidityChart(selectedDate, gridColor, textColor) {
    const chartData = await window.commonUtils.fetchData("/humidity-chart-data", {
      date: selectedDate,
      type: this.systemType,
    });

    const ctx = document.getElementById("humidityChart").getContext("2d");

    if (this.humidityChart) {
      this.humidityChart.destroy();
    }

    this.humidityChart = new Chart(ctx, {
      type: "line",
      data: chartData,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
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
            max: 100
          },
        },
        plugins: {
          legend: { labels: { color: textColor } },
          title: {
            display: true,
            text: 'Grafik Kelembaban Harian (DHT11)',
            color: textColor
          }
        },
      },
    });
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