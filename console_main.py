"""Visible console host for the local web viewer; no Tk window."""

import argparse
import signal
import sys
import time

from system_viewer import SystemWideViewer, ViewerUnavailable
from web_server import BrowserBridge, LocalWebServer


class ConsoleController:
    def __init__(self, bridge, viewer=None):
        self.bridge = bridge
        self.viewer = viewer or SystemWideViewer()
        self.epoch = -1
        self.live = None
        self.error = ""

    def tick(self, allow_monitoring=True):
        owner, epoch, heartbeat, commands = self.bridge.take_commands()
        if epoch != self.epoch:
            self.viewer.stop()
            self.live = None
            self.epoch = epoch
        if owner is None or time.monotonic() - heartbeat >= 3:
            self.viewer.stop()
            commands = []
        if not allow_monitoring:
            self.viewer.stop()
            if "start" in commands:
                self.error = "Restore the visible monitoring window before clicking Start."
            commands = [action for action in commands if action != "start"]
        for action in commands:
            if action == "start":
                self.error = ""
                try:
                    self.viewer.start()
                except ViewerUnavailable as error:
                    self.error = str(error)
            elif action == "stop":
                self.viewer.stop()
                self.live = None
            elif action == "clear":
                self.viewer.clear()
                self.live = None
        snapshot = self.viewer.poll()
        if snapshot is not None:
            self.live = snapshot
        if not self.viewer.enabled or (self.live and self.live.expires_at is not None
                                       and time.monotonic() >= self.live.expires_at):
            self.live = None
        state = {"phase": self.viewer.phase,
                 "key": self.live.combination if self.live else "",
                 "held": list(self.live.held) if self.live else [],
                 "preview": self.viewer.preview,
                 "error": self.error or self.viewer.error}
        self.bridge.publish(state)
        return state

    def close(self):
        self.viewer.stop()
        self.viewer.close()


def main():
    def interrupt(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupt)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupt)
    parser = argparse.ArgumentParser(description="Keyboard Monitor Lab - local web console")
    parser.add_argument("--port", type=int, default=8000)
    # Kept for compatibility with existing launch commands; now always manual.
    parser.add_argument("--no-browser", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    bridge = BrowserBridge()
    server = LocalWebServer(bridge, args.port)
    controller = ConsoleController(bridge)
    print("Keyboard Monitor Lab | Local display only", flush=True)
    print("Stopped. Click Start on the website to monitor. Ctrl+C exits.", flush=True)
    print("Closing the viewer tab stops monitoring. No keys are written to this console or saved.", flush=True)
    previous = None
    try:
        server.start()
        while not server.ready.wait(0.1):
            pass
        if server.failed:
            print(server.failed, flush=True)
            return 1
        print("Open: " + server.browser_url, flush=True)
        print("Open this link manually in your browser when ready.", flush=True)
        while not server.failed:
            state = controller.tick()
            status = (state["phase"], state["error"])
            if status != previous:
                label = {"active": "Monitoring active", "stopped": "Stopped",
                         "starting": "Starting", "stopping": "Stopping", "error": "Stopped - error"}
                print(label.get(status[0], status[0]) + (": " + status[1] if status[1] else ""), flush=True)
                previous = status
            time.sleep(0.05)
        print(server.failed, flush=True)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        controller.close()
        server.close()
        print("Stopped. Service closed.", flush=True)


if __name__ == "__main__":
    result = main()
    if result and sys.stdin.isatty():
        try:
            input("Press Enter to close. ")
        except (EOFError, KeyboardInterrupt):
            pass
    raise SystemExit(result)
