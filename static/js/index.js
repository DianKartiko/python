document.addEventListener("DOMContentLoaded", function () {
            // --- Inisialisasi Elemen HTML ---
            const themeToggle = document.getElementById("theme-toggle");
            const themeText = document.getElementById("theme-text");
            const htmlElement = document.documentElement;
            const dataSection = document.getElementById('data-section');
            const tableBody = document.getElementById('dataTableBody');
            const loadingIndicator = document.getElementById('loadingIndicator');
            const noDataMessage = document.getElementById('noDataMessage');
            const downloadBtn = document.getElementById('downloadBtn');
            const tableCaption = document.getElementById('tableCaption');
            let datepickerInstance = null;

            // --- Fungsi untuk Mengambil Data dari Server ---
            async function fetchData(selectedDateStr) {
                if (!selectedDateStr) return;

                dataSection.style.display = 'none';
                tableBody.innerHTML = '';
                loadingIndicator.style.display = 'block';
                noDataMessage.style.display = 'none';

                try {
                    // Placeholder: Ganti dengan URL endpoint Anda
                    const response = await fetch(`/data?date=${selectedDateStr}`);
                    if (!response.ok) throw new Error(`Gagal mengambil data: ${response.statusText}`);
                    
                    const data = await response.json();
                    loadingIndicator.style.display = 'none';

                    if (data.length === 0) {
                        noDataMessage.style.display = 'block';
                        noDataMessage.textContent = `Tidak ada data tercatat pada tanggal ${selectedDateStr}.`;
                    } else {
                        dataSection.style.display = 'block';
                        const rowData = data[0];
                        tableCaption.textContent = `Data terakhir pada pukul ${rowData.waktu.split(' ')[1]}`;
                        const tr = document.createElement('tr');
                        
                        const dryer1 = rowData.dryer1 !== null ? `${rowData.dryer1}°C` : 'N/A';
                        const dryer2 = rowData.dryer2 !== null ? `${rowData.dryer2}°C` : 'N/A';
                        const dryer3 = rowData.dryer3 !== null ? `${rowData.dryer3}°C` : 'N/A';
                        
                        tr.innerHTML = `<td>${rowData.waktu.split(' ')[1]}</td><td>${dryer1}</td><td>${dryer2}</td><td>${dryer3}</td>`;
                        tableBody.appendChild(tr);
                    }
                } catch (error) {
                    loadingIndicator.style.display = 'none';
                    noDataMessage.textContent = `Error: ${error.message}`;
                    noDataMessage.style.display = 'block';
                    console.error("Fetch error:", error);
                }
            }

            // --- Fungsi Inisialisasi Datepicker (digabung dengan logika tema) ---
            function initFlatpickr(theme) {
                if (datepickerInstance) datepickerInstance.destroy();
                
                let config = {
                    dateFormat: "Y-m-d",
                    defaultDate: "today",
                    onChange: function(selectedDates, dateStr, instance) {
                        fetchData(dateStr);
                    }
                };
                if (theme === 'dark') config.theme = 'dark';
                
                datepickerInstance = flatpickr("#datePicker", config);
            }

            // --- Fungsi untuk Menerapkan Tema ---
            const applyTheme = (theme) => {
                htmlElement.setAttribute("data-bs-theme", theme);
                themeText.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
                initFlatpickr(theme);
            };

            // --- Event Listeners ---
            themeToggle.addEventListener("click", function () {
                const newTheme = htmlElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
                localStorage.setItem("theme", newTheme);
                applyTheme(newTheme);
            });

            downloadBtn.addEventListener('click', function() {
                const selectedDate = datepickerInstance.input.value;
                if (!selectedDate) {
                    console.error('Tanggal tidak valid.');
                    return;
                }
                window.open(`/download?date=${selectedDate}`, '_blank');
            });
            
            // --- Inisialisasi Awal ---
            const savedTheme = localStorage.getItem("theme") || htmlElement.getAttribute('data-bs-theme');
            applyTheme(savedTheme);

            // Muat data awal untuk hari ini setelah inisialisasi
            setTimeout(() => {
                if (datepickerInstance && datepickerInstance.input) {
                    fetchData(datepickerInstance.input.value);
                }
            }, 100); // Timeout singkat memastikan datepicker sudah siap
        });