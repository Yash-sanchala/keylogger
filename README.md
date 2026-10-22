# ⌨️ Keyboard Monitor Lab

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-blue?style=flat-square)](#)

A lightweight, real-time keyboard diagnostic and input monitoring lab built with Python. Features an in-memory capture engine and an interactive local web dashboard with zero disk logging and no external network transmission.

---

## 📌 Table of Contents
- [Overview](#-overview)
- [Key Features](#-key-features)
- [Privacy & Security Guarantees](#-privacy--security-guarantees)
- [Architecture & Tech Stack](#-architecture--tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Running from Source](#running-from-source)
  - [Running with Custom Port](#running-with-custom-port)
- [Building Standalone Executable](#-building-standalone-executable)
- [Running Tests](#-running-tests)
- [Disclaimer](#-disclaimer)

---

## 🔍 Overview

**Keyboard Monitor Lab** provides a local environment for testing keyboard responsiveness, auditing hotkey combinations, and diagnosing input issues. It pairs a local Python backend with an interactive web dashboard running at `http://127.0.0.1:8000/` to visualize active keypresses, held modifier combinations, and rolling character input in real time.

Monitoring is completely opt-in and begins only when the user explicitly clicks **Start monitoring**.

---

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| **⚡ Live Keystroke Stream** | Displays incoming characters in real time within a rolling buffer (latest 48 typed characters) with ultra-low latency. |
| **⌨️ Held Shortcuts Tracker** | Detects and highlights active modifier combinations (`Ctrl`, `Alt`, `Shift`, `Win`) simultaneously. |
| **🖥️ Browser Dashboard** | Clean web UI with one-click **Start**, **Stop**, and **Clear Preview** controls. |
| **🛡️ Auto-Stop Protection** | Interception automatically suspends whenever the browser tab or connection is closed. |
| **📦 Zero Install (Portable)** | Packaged as a standalone Windows executable (`KeyboardMonitorLab.exe`) requiring no Python setup. |

---

## 🔒 Privacy & Security Guarantees

This application is strictly an input testing utility and adheres to safe design practices:

- **In-Memory Only**: Keystrokes exist strictly inside RAM during active capture.
- **Zero Disk Writes**: No log files, text archives, or database records are saved to disk.
- **No Network Transmission**: Runs strictly on `localhost` (`127.0.0.1`). There is zero telemetry, tracking, or remote outbound communication.
- **Explicit Consent**: Capture is disabled on startup and requires manual activation.

---

## 🛠️ Architecture & Tech Stack

```text
[ Physical Keyboard ] 
         │
         ▼
[ low-level Hook / system_viewer.py ] ─── (In-Memory Buffer)
         │
         ▼
[ Local Web Server / web_server.py (127.0.0.1:8000) ]
         │
         ▼
[ Web Frontend / web/ (HTML5 + CSS3 + Vanilla JS) ]
```

- **Backend**: Python 3 (Threading, local HTTP socket server, hook listeners)
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (ES6+)
- **Testing**: Python `unittest` framework covering console launcher, web server routing, keyboard hook logic, and binary smoke testing
- **Packaging**: PyInstaller (`KeyboardMonitorLab.spec`) for portable single-binary distribution

---

## 📂 Project Structure

```text
KeyboardMonitorOnly/
├── web/
│   ├── index.html            # Web dashboard user interface
│   ├── app.js                # Frontend polling, event handlers & state
│   └── style.css             # UI theme and layout styling
├── tests/
│   ├── test_console.py       # Unit tests for console service launcher
│   ├── test_system_viewer.py # Unit tests for keyboard capture engine
│   ├── test_web.py           # Unit tests for HTTP server & endpoints
│   └── smoke_exe.py          # Smoke testing for standalone binary
├── console_main.py           # Main application entry point
├── system_viewer.py          # Keyboard event hooks & state management
├── web_server.py             # Local HTTP server implementation
├── KeyboardMonitorLab.spec   # PyInstaller single-file build specification
├── requirements.txt          # Python package dependencies
├── .gitignore                # Git exclusions (build artifacts, caches)
└── README.md                 # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher installed on Windows
- Git

### Running from Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Yash-sanchala/keylogger.git
   cd keylogger
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the server:**
   ```bash
   python console_main.py
   ```

4. **Open the dashboard:**
   Navigate to **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser and click **Start monitoring**.

### Running with Custom Port

If port `8000` is already in use by another application:
```bash
python console_main.py --port 8001
```
Then navigate to `http://127.0.0.1:8001/`.

---

## 📦 Building Standalone Executable

To bundle the application into a single standalone `.exe` file that runs without requiring Python:

```bash
pip install pyinstaller
python -m PyInstaller --noconfirm --distpath . KeyboardMonitorLab.spec
```

The resulting `KeyboardMonitorLab.exe` will be generated in your project root.

---

## 🧪 Running Tests

Execute the automated test suite using Python's built-in `unittest` runner:

```bash
# Run all unit tests
python -m unittest discover -s tests -p "test_*.py"
```

---

## ⚠️ Disclaimer

This tool is created solely for educational purposes, hardware testing, and keyboard diagnostics. Keystrokes are handled exclusively in transient system memory and are never stored or transmitted.
