document.addEventListener("DOMContentLoaded", function () {
  // --- Inisialisasi Elemen ---
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

  // Elemen untuk data real-time
  const tempElement1 = document.getElementById("current_suhu_1");
  const tempElement2 = document.getElementById("current_suhu_2");
  const tempElement3 = document.getElementById("current_suhu_3");
  const timeElement = document.getElementById("current_time");

  // Elemen dan variabel untuk Chart
  const chartCanvas = document.getElementById("temperatureChart");
  let tempChart = null;

  // --- Fungsi Notifikasi & Stream Notifikasi ---
  function showNotification(title, message) {
    const toastContainer = document.querySelector(".toast-container");
    if (!toastContainer) return;
    const toastId = "toast-" + Math.random().toString(36).substring(2, 9);
    const toastHTML = `
      <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="toast-header">
          <i class="bi bi-bell-fill me-2"></i>
          <strong class="me-auto">${title}</strong>
          <small>Baru saja</small>
          <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">${message}</div>
      </div>`;
    toastContainer.insertAdjacentHTML("beforeend", toastHTML);
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement);
    toastElement.addEventListener("hidden.bs.toast", () =>
      toastElement.remove()
    );
    toast.show();
  }

  function connectToNotificationStream() {
    const eventSource = new EventSource("/stream-notifications");
    eventSource.onmessage = function (event) {
      const notification = JSON.parse(event.data);
      showNotification(notification.title, notification.message);
    };
    eventSource.onerror = function (err) {
      console.error(
        "Koneksi stream notifikasi gagal, mencoba lagi dalam 5 detik...",
        err
      );
      eventSource.close();
      setTimeout(connectToNotificationStream, 5000);
    };
  }

  // --- Stream untuk update suhu real-time ---
  function connectToDataStream() {
    const eventSource = new EventSource("/stream-data");
    eventSource.onmessage = function (event) {
      const data = JSON.parse(event.data);
      if (tempElement1)
        tempElement1.textContent =
          data.dryer1 !== "N/A" ? data.dryer1 + " °C" : "N/A";
      if (tempElement2)
        tempElement2.textContent =
          data.dryer2 !== "N/A" ? data.dryer2 + " °C" : "N/A";
      if (tempElement3)
        tempElement3.textContent =
          data.dryer3 !== "N/A" ? data.dryer3 + " °C" : "N/A";
      if (timeElement) timeElement.textContent = data.time;
    };
    eventSource.onerror = function (err) {
      console.error(
        "Koneksi stream data gagal, mencoba lagi dalam 5 detik...",
        err
      );
      eventSource.close();
      setTimeout(connectToDataStream, 5000);
    };
  }

  // --- Fungsi untuk Chart ---
  function renderChart(chartData, theme) {
    if (!chartCanvas) return;
    const ctx = chartCanvas.getContext("2d");
    if (tempChart) {
      tempChart.destroy();
    }

    const isDark = theme === "dark";
    const gridColor = isDark
      ? "rgba(255, 255, 255, 0.1)"
      : "rgba(0, 0, 0, 0.1)";
    const textColor = isDark ? "#adb5bd" : "#495057";

    const colors = {
      "Dryer 1": {
        border: "rgba(54, 162, 235, 0.9)",
        area: isDark ? "rgba(54, 162, 235, 0.2)" : "rgba(54, 162, 235, 0.3)",
      },
      "Dryer 2": {
        border: "rgba(255, 159, 64, 0.9)",
        area: isDark ? "rgba(255, 159, 64, 0.2)" : "rgba(255, 159, 64, 0.3)",
      },
      "Dryer 3": {
        border: "rgba(255, 99, 132, 0.9)",
        area: isDark ? "rgba(255, 99, 132, 0.2)" : "rgba(255, 99, 132, 0.3)",
      },
    };

    const datasets = chartData.datasets.map((ds) => ({
      label: ds.label,
      data: ds.data,
      borderColor: colors[ds.label].border,
      backgroundColor: colors[ds.label].area,
      fill: true,
      tension: 0.4,
      pointRadius: 0,
      borderWidth: 2,
    }));

    tempChart = new Chart(ctx, {
      type: "line",
      data: { labels: chartData.labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: { legend: { labels: { color: textColor } } },
        scales: {
          x: {
            type: "time",
            time: {
              unit: "hour",
              tooltipFormat: "yyyy-MM-dd HH:mm",
              displayFormats: { hour: "HH:mm" },
            },
            ticks: { color: textColor },
            grid: { color: gridColor },
          },
          y: {
            ticks: { color: textColor },
            grid: { color: gridColor },
            title: { display: true, text: "Suhu (°C)", color: textColor },
          },
        },
      },
    });
  }

  async function fetchChartData(selectedDateStr) {
    try {
      const response = await fetch(`/chart-data?date=${selectedDateStr}`);
      if (!response.ok) throw new Error("Data chart tidak tersedia");
      const chartData = await response.json();
      const currentTheme = htmlElement.getAttribute("data-bs-theme") || "dark";
      renderChart(chartData, currentTheme);
    } catch (error) {
      console.error("Gagal mengambil data chart:", error);
      if (tempChart) tempChart.destroy();
    }
  }

  // --- Fungsi Data Historis untuk Tabel ---
  async function fetchData(selectedDateStr) {
    if (!selectedDateStr) return;
    dataSection.style.display = "none";
    tableBody.innerHTML = "";
    loadingIndicator.style.display = "block";
    noDataMessage.style.display = "none";
    try {
      const response = await fetch(`/data?date=${selectedDateStr}`);
      if (!response.ok)
        throw new Error(`Gagal mengambil data: ${response.statusText}`);
      const data = await response.json();
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

  function initFlatpickr(theme) {
    if (datepickerInstance) datepickerInstance.destroy();
    let config = {
      dateFormat: "Y-m-d",
      defaultDate: "today",
      onChange: function (selectedDates, dateStr) {
        fetchData(dateStr);
        fetchChartData(dateStr);
      },
    };
    if (theme === "dark") config.theme = "dark";
    datepickerInstance = flatpickr("#datePicker", config);
  }

  // --- Fungsi Tema ---
  const applyTheme = (theme) => {
    htmlElement.setAttribute("data-bs-theme", theme);
    if (themeText)
      themeText.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
    initFlatpickr(theme);
    if (datepickerInstance && datepickerInstance.input.value) {
      fetchChartData(datepickerInstance.input.value);
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
      const selectedDate = datepickerInstance.input.value;
      if (selectedDate) {
        window.open(`/download?date=${selectedDate}`, "_blank");
      } else {
        console.error("Tanggal tidak valid untuk diunduh.");
      }
    });
  }

  // --- Inisialisasi Awal ---
  const savedTheme = localStorage.getItem("theme") || "dark";
  applyTheme(savedTheme);

  connectToNotificationStream();
  connectToDataStream();

  // Muat data awal untuk hari ini
  setTimeout(() => {
    if (datepickerInstance && datepickerInstance.input) {
      const today = datepickerInstance.input.value;
      fetchData(today);
      fetchChartData(today);
    }
  }, 100);
});
