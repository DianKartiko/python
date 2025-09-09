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

  // === FUNGSI BARU: Fetch data humidity historis ===
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

    if (!humiditySection) return; // Skip jika elemen tidak ada di halaman

    humiditySection.style.display = "none";
    humidityTableBody.innerHTML = "";
    humidityLoadingIndicator.style.display = "block";
    humidityNoDataMessage.style.display = "none";

    try {
      const response = await fetch(
        `/humidity-data?date=${selectedDateStr}&sensor_id=humidity1`
      );
      if (!response.ok)
        throw new Error(
          `Gagal mengambil data humidity: ${response.statusText}`
        );
      const data = await response.json();
      humidityLoadingIndicator.style.display = "none";

      if (data.length === 0) {
        humidityNoDataMessage.style.display = "block";
        humidityNoDataMessage.textContent = `Tidak ada data humidity tercatat pada tanggal ${selectedDateStr}.`;
      } else {
        humiditySection.style.display = "block";
        humidityTableCaption.textContent = `Menampilkan ${data.length} data humidity untuk ${selectedDateStr}`;
        data.forEach((rowData) => {
          const tr = document.createElement("tr");
          const humidity =
            rowData.humidity !== null
              ? `${rowData.humidity.toFixed(1)}%`
              : "N/A";
          tr.innerHTML = `<td>${rowData.waktu}</td><td>${humidity}</td>`;
          humidityTableBody.appendChild(tr);
        });
      }
    } catch (error) {
      humidityLoadingIndicator.style.display = "none";
      humidityNoDataMessage.textContent = `Error: ${error.message}`;
      humidityNoDataMessage.style.display = "block";
      console.error("Fetch humidity error:", error);
    }
  }

  function initFlatpickr(theme) {
    if (datepickerInstance) datepickerInstance.destroy();
    let config = {
      dateFormat: "Y-m-d",
      defaultDate: "today",
      onChange: function (selectedDates, dateStr) {
        // Panggil fungsi untuk update tabel temperature
        fetchData(dateStr);
        // === TAMBAHAN: Panggil fungsi untuk update tabel humidity ===
        fetchHumidityData(dateStr);
        // Panggil fungsi untuk update chart dengan tema yang sedang aktif
        renderChart(htmlElement.getAttribute("data-bs-theme"));
        // === TAMBAHAN: Panggil fungsi untuk update humidity chart ===
        renderHumidityChart(htmlElement.getAttribute("data-bs-theme"));
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
    // === TAMBAHAN: Render ulang humidity chart dengan tema baru ===
    renderHumidityChart(theme);
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

  // --- FUNGSI ENHANCED: Stream Data Real-time (Temperature + Humidity) ---
  function connectToDataStream() {
    // Ambil elemen-elemen temperature yang akan diupdate
    const suhu1Element = document.getElementById("current_suhu_1");
    const suhu2Element = document.getElementById("current_suhu_2");
    const suhu3Element = document.getElementById("current_suhu_3");

    // === TAMBAHAN: Ambil elemen humidity yang akan diupdate ===
    const humidity1Element = document.getElementById("current_humidity_1");

    // Buat koneksi EventSource ke endpoint stream di Flask
    const eventSource = new EventSource("/stream-data");

    // Definisikan apa yang harus dilakukan ketika pesan diterima
    eventSource.onmessage = function (event) {
      // Parse data JSON yang diterima dari server
      const data = JSON.parse(event.data);
      console.log("Received stream data:", data); // Debugging

      // Update elemen HTML dengan data temperature baru
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

      // === TAMBAHAN: Update elemen HTML dengan data humidity baru ===
      if (humidity1Element) {
        humidity1Element.textContent =
          data.humidity1 !== "N/A" ? `${data.humidity1}%` : "N/A";
        console.log("Updated humidity1 element:", data.humidity1); // Debugging
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
  let humidityChart = null; // === TAMBAHAN: Variable untuk humidity chart ===

  // --- Fungsi untuk merender Temperature Chart ---
  async function renderChart(theme) {
    try {
      // 1. Ambil tanggal yang dipilih saat ini dari input datepicker
      const selectedDate = datepickerInstance.input.value;
      if (!selectedDate) return; // Jangan lakukan apa-apa jika tidak ada tanggal

      // 2. Lakukan fetch ke endpoint dengan menyertakan tanggal sebagai query parameter
      const response = await fetch(`/chart-data?date=${selectedDate}`);
      if (!response.ok) {
        throw new Error(`Gagal mengambil data chart: ${response.statusText}`);
      }
      const chartData = await response.json();

      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode
        ? "rgba(255, 255, 255, 0.1)"
        : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      const ctx = document.getElementById("temperatureChart");
      if (!ctx) return; // Skip jika element tidak ada

      if (temperatureChart) {
        temperatureChart.destroy();
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
      console.error("Gagal merender temperature chart:", error);
    }
  }

  // === FUNGSI BARU: Merender Humidity Chart ===
  async function renderHumidityChart(theme) {
    try {
      const selectedDate = datepickerInstance.input.value;
      if (!selectedDate) return;

      const response = await fetch(`/humidity-chart-data?date=${selectedDate}`);
      if (!response.ok) {
        throw new Error(
          `Gagal mengambil data humidity chart: ${response.statusText}`
        );
      }
      const chartData = await response.json();

      const isDarkMode = theme === "dark";
      const gridColor = isDarkMode
        ? "rgba(255, 255, 255, 0.1)"
        : "rgba(0, 0, 0, 0.1)";
      const textColor = isDarkMode ? "#e9ecef" : "#495057";

      const ctx = document.getElementById("humidityChart");
      if (!ctx) return; // Skip jika element tidak ada

      if (humidityChart) {
        humidityChart.destroy();
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
              labels: {
                color: textColor,
              },
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
      console.error("Gagal merender humidity chart:", error);
    }
  }

  // --- Notification Sounds
  const notificationSound = new Audio("static/sounds/mixkit-long-pop-2358.wav");

  function showNotificationToast(title, message, level = "info") {
    const toastContainer = document.querySelector(".toast-container");
    if (!toastContainer) {
      console.error("Toast container tidak ditemukan di dalam DOM.");
      return;
    }

    // Siapkan ikon SVG berdasarkan level notifikasi
    const icons = {
      success:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check-circle-fill text-success me-2" viewBox="0 0 16 16"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg>',
      warning:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-exclamation-triangle-fill text-warning me-2" viewBox="0 0 16 16"><path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/></svg>',
      danger:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-x-octagon-fill text-danger me-2" viewBox="0 0 16 16"><path d="M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353L11.46.146zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708z"/></svg>',
    };
    const icon = icons[level] || "";

    // 1. Buat elemen HTML untuk Toast secara dinamis
    const toastElement = document.createElement("div");
    toastElement.classList.add("toast");
    toastElement.setAttribute("role", "alert");
    toastElement.setAttribute("aria-live", "assertive");
    toastElement.setAttribute("aria-atomic", "true");

    const now = new Date();
    const timeString = `${now.getHours().toString().padStart(2, "0")}:${now
      .getMinutes()
      .toString()
      .padStart(2, "0")}`;

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

    // 2. Tambahkan Toast yang baru dibuat ke dalam container
    toastContainer.appendChild(toastElement);

    // 3. Inisialisasi Toast menggunakan API Bootstrap dan tampilkan
    const toast = new bootstrap.Toast(toastElement, {
      delay: 15000, // Toast akan hilang secara otomatis setelah 15 detik
    });
    toast.show();

    // 4. Putar suara notifikasi
    // `.catch()` ditambahkan untuk menangani error jika browser memblokir auto-play audio
    notificationSound.play().catch((error) => {
      console.warn("Pemutaran audio dicegah oleh browser:", error);
    });

    // 5. Hapus elemen Toast dari DOM setelah selesai ditampilkan untuk menjaga kebersihan HTML
    toastElement.addEventListener("hidden.bs.toast", () => {
      toastElement.remove();
    });
  }

  /**
   * Fungsi untuk terhubung ke Stream Notifikasi Real-time dari server.
   * Fungsi ini menggunakan EventSource untuk mendengarkan endpoint /stream-notifications.
   */
  function connectToNotificationStream() {
    console.log("[SSE] Mencoba terhubung ke /stream-notifications...");
    const eventSource = new EventSource("/stream-notifications");

    // Event handler ketika koneksi berhasil dibuka
    eventSource.onopen = function () {
      console.log("[SSE] Koneksi ke stream notifikasi BERHASIL dibuat.");
    };

    // Event handler ketika ada pesan baru diterima dari server
    eventSource.onmessage = function (event) {
      // Abaikan pesan heartbeat yang digunakan untuk menjaga koneksi tetap hidup
      if (event.data.includes("heartbeat")) {
        console.log("[SSE] Heartbeat diterima dari server.");
        return;
      }

      console.log("[SSE] Data mentah diterima:", event.data);

      try {
        const data = JSON.parse(event.data);
        console.log("[SSE] Data berhasil di-parse:", data);
        // Panggil fungsi helper untuk menampilkan notifikasi ke UI
        showNotificationToast(data.title, data.message, data.level);
      } catch (e) {
        console.error("[SSE] Gagal mem-parsing data JSON dari server:", e);
      }
    };

    // Event handler ketika terjadi error pada koneksi
    eventSource.onerror = function (err) {
      console.error("[SSE] Terjadi error pada koneksi EventSource:", err);
      eventSource.close();
      console.log(
        "[SSE] Koneksi ditutup karena error, mencoba lagi dalam 5 detik..."
      );
      // Coba sambungkan kembali setelah 5 detik
      setTimeout(connectToNotificationStream, 5000);
    };
  }

  // --- Inisialisasi Stream Connections ---
  connectToNotificationStream();
  connectToDataStream(); // Fungsi enhanced dengan humidity support

  // Muat data awal untuk hari ini
  setTimeout(() => {
    if (datepickerInstance && datepickerInstance.input) {
      const today = datepickerInstance.input.value;
      fetchData(today); // Temperature data
      fetchHumidityData(today); // === TAMBAHAN: Humidity data ===
    }
  }, 100);
});
