# Keyboard Monitor Only

Run **KeyboardMonitorLab.exe** and keep its console open. Then open
http://127.0.0.1:8000/ and click **Start monitoring**.

Displays current keys, held shortcuts, and the latest 48 typed characters.
**Stop** pauses capture. **Clear preview** erases the preview. Closing the
browser tab stops capture. Ctrl+C exits the service.

This folder has no camera or microphone functionality. Keyboard input stays in
memory; no typing is saved to disk or transmitted to an external server.
Monitoring is disabled at startup and requires an explicit Start click.
Physical keyboard operation needs manual verification.

Only one copy can use port 8000. Close another running copy, or launch
`KeyboardMonitorLab.exe --port 8001` and open http://127.0.0.1:8001/.

The executable is standalone and needs no Python installation. Source files,
web assets, dependency list, build specification, and keyboard tests are included.
To run the source with your own Python environment: install requirements.txt,
then run `python console_main.py`.
To rebuild: install PyInstaller, then run
`python -m PyInstaller --noconfirm --distpath . KeyboardMonitorLab.spec`.
