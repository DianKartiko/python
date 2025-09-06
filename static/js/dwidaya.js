// Dwidaya dashboard - comprehensive view of all systems
class DwidayaController {
  constructor() {
    this.allDeviceIds = [
      "dryer1",
      "dryer2",
      "dryer3",
      "kedi1",
      "kedi2",
      "boiler1",
      "boiler2",
      "kelembaban4",
    ];
  }

  init() {
    this.connectToDataStream();
    this.setupStatusIndicators();
  }

  connectToDataStream() {
    const eventSource = new EventSource("/stream-data");

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.updateAllDisplays(data);
      this.updateSystemStatus(data);
    };

    eventSource.onerror = (err) => {
      console.error("Dwidaya stream connection error:", err);
      eventSource.close();
      // Show connection error status
      this.showConnectionError();
    };
  }

  updateAllDisplays(data) {
    this.allDeviceIds.forEach((deviceId) => {
      const element = document.getElementById(`current_${deviceId}`);
      if (element && data[deviceId]) {
        const temperature = data[deviceId];
        element.textContent =
          temperature !== "N/A" ? `${temperature}°C` : "N/A";

        // Add temperature-based styling
        this.updateTemperatureStatus(element, temperature, deviceId);
      }
    });

    // Update timestamp
    const timestampElement = document.getElementById("last_update");
    if (timestampElement) {
      const now = new Date();
      timestampElement.textContent = `Last update: ${now.toLocaleTimeString()}`;
    }
  }

  updateTemperatureStatus(element, temperature, deviceId) {
    // Remove existing status classes
    element.classList.remove("temp-normal", "temp-warning", "temp-danger");

    if (temperature === "N/A") {
      element.classList.add("temp-offline");
      return;
    }

    const temp = parseFloat(temperature);

    // Define temperature thresholds based on device type
    let minTemp, maxTemp;
    if (deviceId.startsWith("dryer")) {
      minTemp = 120;
      maxTemp = 155;
    } else if (deviceId.startsWith("kedi")) {
      minTemp = 100; // Adjust based on your kedi requirements
      maxTemp = 140;
    } else if (deviceId.startsWith("boiler")) {
      minTemp = 80; // Adjust based on your boiler requirements
      maxTemp = 120;
    }

    element.classList.remove("temp-offline");

    if (temp < minTemp || temp > maxTemp) {
      element.classList.add("temp-danger");
    } else if (temp < minTemp + 10 || temp > maxTemp - 10) {
      element.classList.add("temp-warning");
    } else {
      element.classList.add("temp-normal");
    }
  }

  updateSystemStatus(data) {
    const systems = {
      dryer: ["dryer1", "dryer2", "dryer3"],
      kedi: ["kedi1", "kedi2"],
      boiler: ["boiler1", "boiler2"],
    };

    Object.keys(systems).forEach((systemName) => {
      const devices = systems[systemName];
      const statusElement = document.getElementById(`${systemName}_status`);

      if (statusElement) {
        const systemStatus = this.calculateSystemStatus(data, devices);
        this.updateStatusIndicator(statusElement, systemStatus);
      }
    });
  }

  calculateSystemStatus(data, devices) {
    let onlineCount = 0;
    let warningCount = 0;
    let errorCount = 0;

    devices.forEach((deviceId) => {
      const temp = data[deviceId];
      if (temp === "N/A") {
        return; // Offline device
      }

      onlineCount++;
      const temperature = parseFloat(temp);

      // Simple status check - adjust thresholds as needed
      if (temperature < 80 || temperature > 180) {
        errorCount++;
      } else if (temperature < 100 || temperature > 160) {
        warningCount++;
      }
    });

    if (errorCount > 0) return "error";
    if (warningCount > 0) return "warning";
    if (onlineCount > 0) return "normal";
    return "offline";
  }

  updateStatusIndicator(element, status) {
    // Remove existing status classes
    element.classList.remove(
      "status-normal",
      "status-warning",
      "status-error",
      "status-offline"
    );

    // Add new status class
    element.classList.add(`status-${status}`);

    // Update status text and icon
    const statusText = element.querySelector(".status-text");
    const statusIcon = element.querySelector(".status-icon");

    if (statusText && statusIcon) {
      switch (status) {
        case "normal":
          statusText.textContent = "Normal";
          statusIcon.innerHTML = "✓";
          break;
        case "warning":
          statusText.textContent = "Warning";
          statusIcon.innerHTML = "⚠";
          break;
        case "error":
          statusText.textContent = "Error";
          statusIcon.innerHTML = "✗";
          break;
        case "offline":
          statusText.textContent = "Offline";
          statusIcon.innerHTML = "○";
          break;
      }
    }
  }

  setupStatusIndicators() {
    // Add event listeners for status cards if needed
    const statusCards = document.querySelectorAll(".system-status-card");
    statusCards.forEach((card) => {
      card.addEventListener("click", (e) => {
        const systemType = card.dataset.system;
        if (systemType) {
          // Navigate to specific system page
          window.location.href = `/${systemType}`;
        }
      });
    });
  }

  showConnectionError() {
    const errorElement = document.getElementById("connection_status");
    if (errorElement) {
      errorElement.style.display = "block";
      errorElement.innerHTML = `
        <div class="alert alert-danger" role="alert">
          <i class="bi bi-exclamation-triangle"></i>
          Connection to server lost. Trying to reconnect...
        </div>
      `;
    }

    // Try to reconnect after 5 seconds
    setTimeout(() => {
      this.connectToDataStream();
    }, 5000);
  }
}

// Initialize dwidaya controller when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  const dwidayaController = new DwidayaController();
  dwidayaController.init();
});
