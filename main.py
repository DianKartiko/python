#!/usr/bin/env python3
"""
Main entry point untuk Temperature Monitoring System
Modular architecture dengan separation of concerns
"""

from core.monitor import TemperatureMonitor

if __name__ == "__main__":
    monitor = TemperatureMonitor()
    monitor.run()