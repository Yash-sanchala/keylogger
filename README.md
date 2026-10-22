# Keylogger

Overview

Keyboard Monitor Lab is a lightweight, local keyboard activity and keystroke monitoring application designed for hardware testing, debugging, and input diagnostics. It pairs a local Python backend with an interactive web-based dashboard running locally (http://127.0.0.1:8000/) to visualize active keypresses, held modifier combinations, and rolling character input in real time.

Key Features
Live Keystroke Streaming: Dynamically displays incoming keystrokes in a rolling preview buffer (latest 48 typed characters) with low latency.
Held Shortcuts & Modifier Tracking: Detects and highlights active multi-key combinations and modifiers (e.g., Ctrl, Alt, Shift, Win) simultaneously.
Interactive Web Interface: A clean, responsive browser-based UI featuring:
Start / Stop Monitoring: Safe, manual control over capture sessions.
Clear Preview: One-click buffer reset to erase typed history from screen and memory.
Auto-Stop on Exit: Automatically pauses capture when the browser tab is closed.
Privacy & Safety First:
In-Memory Only: Keystrokes exist strictly in RAM during an active session.
Zero Disk Logging: No log files, text dumps, or keystroke records are saved to the hard drive.
No External Network Calls: Operates 100% offline on localhost with zero telemetry or remote server communication.
Standalone Portable Build: Can be packaged as a standalone Windows executable (KeyboardMonitorLab.exe) using PyInstaller, running without requiring a local Python installation.
Technical Stack
Backend: Python 3 (Threading, local HTTP/Socket server, keyboard event listeners)
Frontend: Vanilla JavaScript (ES6+), HTML5, CSS3
Testing: Python unittest suite covering console launcher, web server routing, keyboard hook logic, and binary smoke testing
Packaging: PyInstaller specification (KeyboardMonitorLab.spec) for portable single-binary distribution
How It Works
Service Initialization: Launching the backend (console_main.py or KeyboardMonitorLab.exe) boots a local web server bound to 127.0.0.1:8000.
Explicit Consent & Activation: Monitoring starts in an inactive state by default. The user opens the local dashboard and explicitly clicks Start Monitoring.
Event Processing: The backend captures low-level keyboard events, formats key states and shortcut combos, and pushes them to the web frontend.
Session Teardown: Clicking Stop, closing the browser tab, or pressing Ctrl + C in the terminal immediately halts event interception and flushes the memory buffer.
Repository Structure
text
├── web/
│   ├── index.html            # Web dashboard interface
│   ├── app.js                # Frontend polling, event handlers & UI rendering
│   └── style.css             # Dashboard styling
├── tests/
│   ├── test_console.py       # Console launcher unit tests
│   ├── test_system_viewer.py # Monitoring & event listener logic tests
│   ├── test_web.py           # Web server endpoint and route tests
│   └── smoke_exe.py          # Standalone executable smoke testing
├── console_main.py           # Main application entry point
├── system_viewer.py          # Keyboard event hooks & state management
├── web_server.py             # Local HTTP server implementation
├── KeyboardMonitorLab.spec   # PyInstaller packaging configuration
├── requirements.txt          # Python dependencies
├── .gitignore                # Ignore rules (excludes builds & binaries)
└── README.md                 # Quick start instructions
Setup & Running
Option 1: Running from Source
bash
# 1. Clone repository
git clone https://github.com/Yash-sanchala/keylogger.git
cd keylogger
# 2. Install dependencies
pip install -r requirements.txt
# 3. Start the application
python console_main.py

Open http://127.0.0.1:8000/ in your browser and click Start monitoring.

Option 2: Building the Executable
bash
pip install pyinstaller
python -m PyInstaller --noconfirm --distpath . KeyboardMonitorLab.spec
