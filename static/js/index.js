document.addEventListener('DOMContentLoaded', function() {
            // Data simulasi yang lebih lengkap
            const mockData = [
                // Data untuk hari ini (28 Ags 2025)
                { waktu: '2025-08-28 12:10:15', dryer1: 71.5, dryer2: 74.5, dryer3: 77.0 },
                { waktu: '2025-08-28 12:20:18', dryer1: 72.1, dryer2: 75.1, dryer3: 77.5 },
                { waktu: '2025-08-28 12:30:20', dryer1: 72.8, dryer2: 75.8, dryer3: 78.2 },
                // Data untuk kemarin (27 Ags 2025)
                { waktu: '2025-08-27 10:00:00', dryer1: 70.0, dryer2: 72.0, dryer3: 74.0 },
                { waktu: '2025-08-27 11:00:00', dryer1: 70.5, dryer2: 73.1, dryer3: 75.1 },
                // Data untuk lusa (26 Ags 2025)
                { waktu: '2025-08-26 15:00:00', dryer1: 68.5, dryer2: 70.5, dryer3: 72.5 },
            ];
            
            const dataSection = document.getElementById('data-section');
            const tableBody = document.getElementById('dataTableBody');
            const loadingIndicator = document.getElementById('loadingIndicator');
            const noDataMessage = document.getElementById('noDataMessage');
            const downloadBtn = document.getElementById('downloadBtn');
            const tableCaption = document.getElementById('tableCaption');

            function fetchData(selectedDateStr) {
                if (!selectedDateStr) { return; }

                dataSection.style.display = 'none';
                tableBody.innerHTML = '';
                loadingIndicator.style.display = 'block';
                noDataMessage.style.display = 'none';

                // Simulasi delay jaringan
                setTimeout(() => {
                    const selectedDate = new Date(selectedDateStr);
                    const startDate = new Date(selectedDate);
                    startDate.setHours(0, 0, 0, 0);
                    const endDate = new Date(selectedDate);
                    endDate.setHours(23, 59, 59, 999);

                    const filteredData = mockData.filter(item => {
                        const itemDate = new Date(item.waktu);
                        return itemDate >= startDate && itemDate <= endDate;
                    });

                    loadingIndicator.style.display = 'none';

                    if (filteredData.length === 0) {
                        noDataMessage.style.display = 'block';
                    } else {
                        dataSection.style.display = 'block';
                        tableCaption.textContent = `Menampilkan ${filteredData.length} rekaman data`;
                        filteredData.sort((a, b) => new Date(b.waktu) - new Date(a.waktu));
                        filteredData.forEach(row => {
                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td>${row.waktu.split(' ')[1]}</td>
                                <td>${row.dryer1}°C</td>
                                <td>${row.dryer2}°C</td>
                                <td>${row.dryer3}°C</td>`;
                            tableBody.appendChild(tr);
                        });
                    }
                }, 800);
            }

            const datePicker = flatpickr("#datePicker", {
                theme: "dark",
                dateFormat: "Y-m-d",
                defaultDate: "today",
                onChange: function(selectedDates, dateStr, instance) {
                    fetchData(dateStr);
                }
            });

            downloadBtn.addEventListener('click', function() {
                const selectedDate = datePicker.input.value;
                if (!selectedDate) {
                    alert('Tanggal tidak valid.');
                    return;
                }
                alert(`Akan memulai download data Excel untuk tanggal: ${selectedDate}`);
                window.open(`/download?start=${selectedDate}&end=${selectedDate}`, '_blank');
            });
            
            // Muat data awal untuk hari ini
            fetchData(datePicker.input.value);
        });