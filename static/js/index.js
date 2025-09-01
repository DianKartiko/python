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
    // **BARIS PENTING**: Render ulang chart dengan tema baru
    renderChart(theme);
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

  // --- Fungsi untuk terhubung ke Stream Data Real-time ---
  function connectToDataStream() {
    // Ambil elemen-elemen yang akan diupdate
    const suhu1Element = document.getElementById("current_suhu_1");
    const suhu2Element = document.getElementById("current_suhu_2");
    const suhu3Element = document.getElementById("current_suhu_3");

    // Buat koneksi EventSource ke endpoint stream di Flask
    const eventSource = new EventSource("/stream-data");

    // Definisikan apa yang harus dilakukan ketika pesan diterima
    eventSource.onmessage = function (event) {
      // Parse data JSON yang diterima dari server
      const data = JSON.parse(event.data);

      // Update elemen HTML dengan data baru
      // Cek apakah elemennya ada sebelum mengubah isinya
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
    };

    // Handle jika terjadi error koneksi
    eventSource.onerror = function (err) {
      console.error("EventSource failed:", err);
      // Bisa tambahkan logika untuk mencoba koneksi ulang di sini
      eventSource.close(); // Tutup koneksi yang error
    };
  }

  // Variabel global untuk menyimpan instance chart
  let temperatureChart = null;

  // --- Fungsi untuk merender Chart ---
  async function renderChart(theme) {
    try {
      // Ambil data dari endpoint baru kita
      const response = await fetch("/chart-data");
      if (!response.ok) {
        throw new Error(`Gagal mengambil data chart: ${response.statusText}`);
      }
      const chartData = await response.json();

      // Tentukan warna berdasarkan tema
      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode
        ? "rgba(255, 255, 255, 0.1)"
        : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      const ctx = document.getElementById("temperatureChart").getContext("2d");

      // Jika chart sudah ada, hancurkan dulu untuk menggambar ulang (berguna saat ganti tema)
      if (temperatureChart) {
        temperatureChart.destroy();
      }

      // Buat chart baru
      temperatureChart = new Chart(ctx, {
        type: "line", // Tipe chart
        data: chartData, // Data dari server
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: "index",
            intersect: false,
          },
          scales: {
            x: {
              grid: {
                color: gridColor,
              },
              ticks: {
                color: textColor,
              },
            },
            y: {
              grid: {
                color: gridColor,
              },
              ticks: {
                color: textColor,
                // Format ticks agar ada '°C'
                callback: function (value) {
                  return value + "°C";
                },
              },
            },
          },
          plugins: {
            legend: {
              labels: {
                color: textColor,
              },
            },
          },
        },
      });
    } catch (error) {
      console.error("Gagal merender chart:", error);
      // Anda bisa menampilkan pesan error di UI di sini
    }
  }

  connectToDataStream(); // Fungsi yang baru saja kita buat
  // Muat data awal untuk hari ini
  setTimeout(() => {
    if (datepickerInstance && datepickerInstance.input) {
      const today = datepickerInstance.input.value;
      fetchData(today);
    }
  }, 100);
});
