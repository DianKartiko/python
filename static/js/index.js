document.addEventListener("DOMContentLoaded", function () {
  // --- Inisialisasi Elemen ---
  const themeToggle = document.getElementById("theme-toggle");
  const themeText = document.getElementById("theme-text");
  const htmlElement = document.documentElement;
  const locationToggle = document.getElementById("location-toggle");
  const locationText = document.getElementById("location-text");
  const dataSection = document.getElementById("data-section");
  const tableBody = document.getElementById("dataTableBody");
  const loadingIndicator = document.getElementById("loadingIndicator");
  const noDataMessage = document.getElementById("noDataMessage");
  const downloadBtn = document.getElementById("downloadBtn");
  const tableCaption = document.getElementById("tableCaption");
  let datepickerInstance = null;

  // --- Fungsi Notifikasi & Stream Notifikasi ---
  function showNotification(title, message) {
    const toastContainer = document.querySelector(".toast-container");
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
  function connectToTemperatureStream() {
    const eventSource = new EventSource("/stream-temperatures");
    eventSource.onmessage = function (event) {
      const tempData = JSON.parse(event.data);
      const dryerId = tempData.dryer_id;
      const temperature = tempData.temperature;
      const time = tempData.time;
      const tempElement = document.getElementById(`temp-display-${dryerId}`);
      if (tempElement) tempElement.textContent = temperature;
      const timeElement = document.getElementById("time-display");
      if (timeElement) timeElement.textContent = time;
    };
    eventSource.onerror = function (err) {
      console.error(
        "Koneksi stream suhu gagal, mencoba lagi dalam 5 detik...",
        err
      );
      eventSource.close();
      setTimeout(connectToTemperatureStream, 5000);
    };
  }

  // --- Fungsi Data Historis ---
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
        const rowData = data[0];
        tableCaption.textContent = `Data terakhir pada pukul ${
          rowData.waktu.split(" ")[1]
        }`;
        const tr = document.createElement("tr");
        const dryer1 =
          rowData.dryer1 !== null ? `${rowData.dryer1.toFixed(1)}°C` : "N/A";
        const dryer2 =
          rowData.dryer2 !== null ? `${rowData.dryer2.toFixed(1)}°C` : "N/A";
        const dryer3 =
          rowData.dryer3 !== null ? `${rowData.dryer3.toFixed(1)}°C` : "N/A";
        tr.innerHTML = `<td>${
          rowData.waktu.split(" ")[1]
        }</td><td>${dryer1}</td><td>${dryer2}</td><td>${dryer3}</td>`;
        tableBody.appendChild(tr);
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
      },
    };
    if (theme === "dark") config.theme = "dark";
    datepickerInstance = flatpickr("#datePicker", config);
  }

  // --- Fungsi Utilitas & Tema ---
  const setupNavigation = () => {
    const currentPath = window.location.pathname;
    locationText.textContent = currentPath.includes("/dwidaya")
      ? "Ke Wijaya"
      : "Ke Dwidaya";
    locationToggle.href = currentPath.includes("/dwidaya") ? "/" : "/dwidaya";
  };
  const applyTheme = (theme) => {
    htmlElement.setAttribute("data-bs-theme", theme);
    themeText.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
    initFlatpickr(theme);
  };

  // --- Event Listeners ---
  themeToggle.addEventListener("click", function () {
    const newTheme =
      htmlElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    localStorage.setItem("theme", newTheme);
    applyTheme(newTheme);
  });
  downloadBtn.addEventListener("click", function () {
    const selectedDate = datepickerInstance.input.value;
    if (selectedDate) {
      window.open(`/download?date=${selectedDate}`, "_blank");
    } else {
      console.error("Tanggal tidak valid untuk diunduh.");
    }
  });

  // --- INISIALISASI SAAT HALAMAN DIMUAT ---
  const savedTheme = localStorage.getItem("theme") || "dark";
  applyTheme(savedTheme);
  setupNavigation();
  connectToNotificationStream();
  connectToTemperatureStream();

  // Muat data awal untuk hari ini
  setTimeout(() => {
    if (datepickerInstance && datepickerInstance.input) {
      fetchData(datepickerInstance.input.value);
    }
  }, 100);
});
