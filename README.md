# Bank Security System 🏦

A dual-component hardware and software security monitoring system tailored for bank environments. It integrates an STM32 L476RG microcontroller with a Python-based graphical user interface (GUI) to provide real-time intrusion detection, day/night mode scheduling, and interactive visual alerts.

## Project Overview

This project consists of:
1. **Python GUI (Tkinter)**: A desktop application acting as the control panel. It allows users to set alarm schedules, monitor live UART logs, and visualize the bank's floor plan with dynamic alerts (e.g., flash and ripple effects upon intrusion).
2. **STM32 Firmware (C)**: Embedded code for the STM32 L476RG. It leverages a VL53L8CX Time-of-Flight (ToF) proximity sensor for detecting unauthorized access, an RTC (Real-Time Clock) for time-based alarm scheduling, and a buzzer/LED for physical alerts.

## Features

- **Real-Time Monitoring**: Proximity sensing using the VL53L8CX ToF sensor to detect intruders within a specified threshold (e.g., < 300mm).
- **Time-Based Access Control**:
  - **Day Mode (09:00 - 17:00)**: Secures critical zones like the Vault and Cashier desks.
  - **Night Mode (17:01 - 08:59)**: Arms all zones, providing perimeter and internal security.
- **Interactive Floor Plan GUI**: Visual representation of bank zones (Vault, ATM, Cashier, Customer, Entry) with color-coded status indicators (Secure, Unsecured, Idle, Alert).
- **Dynamic Visual Alerts**: Triggers flashing zone indicators and expanding ripple animations on the GUI when an intrusion is detected.
- **Hardware Alerts**: Activates an onboard LED and a PWM-driven buzzer on the STM32 upon detection.
- **UART Communication**: Robust two-way serial communication between the PC and STM32 for configuring schedules and receiving telemetry.

## Hardware Requirements

- **Microcontroller**: STM32 L476RG Nucleo Board
- **Sensor**: VL53L8CX Time-of-Flight (ToF) 8x8 multizone ranging sensor
- **Actuators**: 
  - Buzzer (Connected via PWM on TIM2)
  - LED (Connected to GPIO)
- **Interface**: USB Cable for Serial/UART communication with PC

## Software Dependencies

**Python (PC GUI)**
- Python 3.x
- `tkinter` (Usually bundled with Python)
- `pyserial` (`pip install pyserial`)

**STM32 (Firmware)**
- STM32CubeIDE or compatible ARM Cortex-M toolchain
- STM32 HAL Libraries
- VL53L8CX ULD (Ultra Lite Driver) API

## System Setup and Usage

### 1. Hardware Setup
- Connect the VL53L8CX sensor to the STM32 via I2C1 (`PB8` / `PB9`).
- Connect the Buzzer to the designated PWM pin.
- Connect the STM32 Nucleo to your computer via USB.

### 2. Flashing the Firmware
- Compile the provided `main.c` (along with standard HAL and VL53L8CX drivers) using STM32CubeIDE.
- Flash the compiled binary to the STM32 L476RG.

### 3. Running the Control Panel
1. Install the required Python package:
   ```bash
   pip install pyserial
   ```
2. Run the GUI application
    ```python bank_security_gui.py```

3. In the GUI:
    1. Select the correct COM Port for your STM32 and click CONNECT.
    2. Input the Current Time, Enable (Night) time, and Disable (Day) time.
    3. Click Set All Times to sync the schedule with the STM32's RTC.
    4. Click Start Monitoring to begin intrusion detection.

## Communication Protocol

The system uses a simple UART serial protocol at 115200 baud.

    - 1, 2, 3: Menu commands from GUI to set Current Time, Enable Time, and Disable Time respectively.
    - 4: Start Monitoring command.
    - 6: Auto-arm command (defaults to 22:00 - 07:00).
    - The STM32 sends formatted string logs (e.g., *** DETECTED! ***) parsed by the Python GUI to trigger graphical alerts.