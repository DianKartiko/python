document.addEventListener('DOMContentLoaded', function() {
    // --- Inisialisasi Elemen HTML ---
    const dataSection = document.getElementById('data-section');
    const tableBody = document.getElementById('dataTableBody');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const noDataMessage = document.getElementById('noDataMessage');
    const downloadBtn = document.getElementById('downloadBtn');
    const tableCaption = document.getElementById('tableCaption');

    // --- Fungsi Utama untuk Mengambil Data dari Server Python ---
    async function fetchData(selectedDateStr) {
        if (!selectedDateStr) { return; }

        // Tampilkan loading dan sembunyikan data lama
        dataSection.style.display = 'none';
        tableBody.innerHTML = '';
        loadingIndicator.style.display = 'block';
        noDataMessage.style.display = 'none';

        try {
            // Panggil endpoint /data di server Flask Anda
            // Server akan mengirimkan 1 data terbaru untuk tanggal ini
            const response = await fetch(`/data?date=${selectedDateStr}`);
            if (!response.ok) {
                throw new Error(`Gagal mengambil data: ${response.statusText}`);
            }
            const data = await response.json(); // Ini akan berisi 0 atau 1 data

            loadingIndicator.style.display = 'none';

            if (data.length === 0) {
                noDataMessage.style.display = 'block';
                noDataMessage.textContent = `Tidak ada data tercatat pada tanggal ${selectedDateStr}.`;
            } else {
                dataSection.style.display = 'block';
                const rowData = data[0]; // Ambil satu-satunya data
                
                tableCaption.textContent = `Data terakhir pada pukul ${rowData.waktu.split(' ')[1]}`;
                
                // Buat satu baris tabel
                const tr = document.createElement('tr');
                
                const dryer1 = rowData.dryer1 !== null ? `${rowData.dryer1}°C` : 'N/A';
                const dryer2 = rowData.dryer2 !== null ? `${rowData.dryer2}°C` : 'N/A';
                const dryer3 = rowData.dryer3 !== null ? `${rowData.dryer3}°C` : 'N/A';
                
                tr.innerHTML = `
                    <td>${rowData.waktu.split(' ')[1]}</td>
                    <td>${dryer1}</td>
                    <td>${dryer2}</td>
                    <td>${dryer3}</td>`;
                tableBody.appendChild(tr);
            }
        } catch (error) {
            loadingIndicator.style.display = 'none';
            noDataMessage.textContent = `Error: ${error.message}`;
            noDataMessage.style.display = 'block';
            console.error("Fetch error:", error);
        }
    }

    // --- Inisialisasi Datepicker ---
    const datePicker = flatpickr("#datePicker", {
        theme: "dark",
        dateFormat: "Y-m-d",
        defaultDate: "today",
        // Setiap kali tanggal diubah, panggil fungsi fetchData
        onChange: function(selectedDates, dateStr, instance) {
            fetchData(dateStr);
        }
    });

    // --- Event Listener untuk Tombol Download ---
    downloadBtn.addEventListener('click', function() {
        const selectedDate = datePicker.input.value;
        if (!selectedDate) {
            alert('Tanggal tidak valid.');
            return;
        }
        // Buka URL /download di server Flask untuk memulai download semua data
        window.open(`/download?date=${selectedDate}`, '_blank');
    });
    
    // --- Muat data awal untuk hari ini saat halaman pertama kali dibuka ---
    fetchData(datePicker.input.value);
});
