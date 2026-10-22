"""Optional system-wide live display. No history, files, timestamps or Tk calls."""

from dataclasses import dataclass
import os
from queue import Empty, Queue
import sys
from threading import Event, Lock
import time


class ViewerUnavailable(RuntimeError):
    """A user-actionable listener or environment problem."""


def listener_factory(**callbacks):
    if sys.platform not in ("win32", "darwin", "linux"):
        raise ViewerUnavailable("System-wide viewing is unsupported on this operating system.")
    if sys.platform == "linux":
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            raise ViewerUnavailable("Wayland is unsupported for system-wide viewing. Use an X11 desktop session or focused-window mode.")
        if not os.environ.get("DISPLAY"):
            raise ViewerUnavailable("An active X11 desktop with DISPLAY set is required. Headless sessions are unsupported.")
    if os.environ.get("PYNPUT_BACKEND") or os.environ.get("PYNPUT_BACKEND_KEYBOARD"):
        raise ViewerUnavailable("Custom pynput backends are unsupported. Unset PYNPUT_BACKEND and PYNPUT_BACKEND_KEYBOARD.")
    try:
        from pynput import keyboard
    except ImportError as error:
        raise ViewerUnavailable("Cannot load pynput. Install dependencies with: python -m pip install -r requirements.txt. On Linux, also check the X11 display connection.") from error
    if sys.platform == "darwin" and not keyboard.Listener.IS_TRUSTED:
        raise ViewerUnavailable("macOS permission is missing. Enable Input Monitoring and Accessibility for the terminal/Python app in System Settings > Privacy & Security, then restart the app.")
    return keyboard.Listener(suppress=False, **callbacks)


MODIFIERS = {"ctrl": "Ctrl", "ctrl_l": "Ctrl", "ctrl_r": "Ctrl",
             "shift": "Shift", "shift_l": "Shift", "shift_r": "Shift",
             "alt": "Alt", "alt_l": "Alt", "alt_r": "Alt", "alt_gr": "AltGr",
             "cmd": "Super/Command", "cmd_l": "Super/Command", "cmd_r": "Super/Command"}
MODIFIER_ORDER = ("Ctrl", "Shift", "Alt", "AltGr", "Super/Command")
PREVIEW_LIMIT = 48


def key_identity(key):
    """Use a stable physical code when supplied, even if Shift changes char."""
    if key is None:
        return ("unknown",), "Unknown key"
    name = getattr(key, "name", None)
    if name:
        label = MODIFIERS.get(name, {"esc": "Escape", "page_up": "Page Up",
                                    "page_down": "Page Down"}.get(name, name.replace("_", " ").title()))
        return ("special", name), label
    char = getattr(key, "char", None)
    vk = getattr(key, "vk", None)
    if char and len(char) == 1 and 1 <= ord(char) <= 26:
        char = chr(ord(char) + 64)  # Ctrl+A can arrive as U+0001.
    label = char if char and char.isprintable() else f"Key {vk}" if vk is not None else "Unknown key"
    identity = ("vk", vk) if vk is not None else ("char", (char or "").casefold())
    return identity, label


@dataclass(frozen=True)
class LiveSnapshot:
    combination: str
    held: tuple[str, ...]
    expires_at: float | None
    preview: str = ""


class SystemWideViewer:
    """Main thread owns lifecycle; callbacks publish only a current snapshot.

    One-slot coalescing avoids collecting a queue of typed key history. The
    callback lock protects only small in-memory operations, never I/O or Tk.
    """

    def __init__(self, factory=listener_factory):
        self._factory = factory
        self._listener = None
        self._cancel = Event()
        self._cancel.set()
        self._lock = Lock()
        self._held = {}
        self._preview = ""
        self._queue = Queue(maxsize=1)
        self.phase = "stopped"
        self.error = ""
        self._started_at = 0.0

    @property
    def enabled(self):
        return self.phase in ("starting", "active")

    @property
    def preview(self):
        with self._lock:
            return self._preview

    def start(self):
        if self.enabled:
            return
        if self._listener is not None and self._listener.is_alive():
            raise ViewerUnavailable("The previous listener is still stopping. Try Start again in a moment.")
        self._reset_live()
        self.error = ""
        self._cancel = Event()
        cancel = self._cancel  # Session-specific gate rejects callbacks from old listeners.
        self.phase = "starting"
        self._started_at = time.monotonic()
        try:
            self._listener = self._factory(
                on_press=lambda key: self._receive(key, True, cancel),
                on_release=lambda key: self._receive(key, False, cancel))
            self._listener.start()
        except Exception as error:
            self.stop()
            self.phase = "error"
            self.error = str(error) if isinstance(error, ViewerUnavailable) else "The keyboard listener could not start. Check desktop support and OS permissions."
            raise ViewerUnavailable(self.error) from error

    def _receive(self, key, pressed, cancel):
        if cancel.is_set():
            return False
        with self._lock:
            if cancel.is_set():
                return False
            now = time.monotonic()
            identity, label = key_identity(key)
            before = self._combination()
            if pressed:
                self._held[identity] = label
                self._preview_key(key)
            else:
                self._held.pop(identity, None)
            current = self._combination()
            snapshot = LiveSnapshot(current or before or label, tuple(self._held.values()),
                                    None if self._held else now + 0.30,
                                    self._preview)
            # Callback is the sole producer; clear()/poll() can only remove.
            try:
                self._queue.get_nowait()
            except Empty:
                pass
            self._queue.put_nowait(snapshot)

    def _preview_key(self, key):
        # A bounded display string, not an event list or document copy.
        # Shortcut letters are not text; Shift alone still permits normal typing.
        if any(label in self._held.values() for label in ("Ctrl", "Alt", "Super/Command")):
            return
        name = getattr(key, "name", None)
        char = getattr(key, "char", None)
        if name == "backspace":
            self._preview = self._preview[:-1]
        elif name == "space":
            self._preview += " "
        elif name in ("enter", "tab"):
            self._preview += "↵" if name == "enter" else "⇥"
        elif char and char.isprintable():
            self._preview += char
        else:
            return
        self._preview = self._preview[-PREVIEW_LIMIT:]

    def _combination(self):
        labels = tuple(dict.fromkeys(self._held.values()))
        ordered = [name for name in MODIFIER_ORDER if name in labels]
        ordered.extend(name for name in labels if name not in MODIFIER_ORDER)
        return " + ".join(ordered)

    def clear(self):
        self._reset_live(clear_preview=True)

    def _reset_live(self, clear_preview=False):
        with self._lock:
            self._held.clear()
            if clear_preview:
                self._preview = ""
            try:
                self._queue.get_nowait()
            except Empty:
                pass

    def stop(self):
        # Gate first, before asking the backend to stop. Late callbacks cannot
        # publish or repopulate the display after the user's Stop click.
        self._cancel.set()
        self._reset_live()
        if self._listener is not None:
            self._listener.stop()
        self.phase = "stopping" if self._listener is not None and self._listener.is_alive() else "stopped"

    def poll(self):
        """Called only by Tk's main thread; also detects backend termination."""
        if self._listener is not None:
            alive = self._listener.is_alive()
            if self.phase == "stopping" and not alive:
                self.phase = "stopped"
            elif self.enabled and not alive:
                self.stop()
                self.phase = "error"
                self.error = "The keyboard listener stopped unexpectedly. Check OS permissions and desktop support, then click Start to retry."
                try:
                    self._listener.join(timeout=0)
                except Exception:
                    pass  # Do not expose key-related exception payloads.
            elif self.phase == "starting":
                if self._listener.running:
                    self.phase = "active"
                elif time.monotonic() - self._started_at > 5:
                    self.stop()
                    self.phase = "error"
                    self.error = "The keyboard listener did not start within 5 seconds. Check OS permissions."
        try:
            return self._queue.get_nowait() if self.enabled else None
        except Empty:
            return None

    def close(self):
        self.stop()
        self.clear()
        if self._listener is not None and self._listener.ident is not None:
            try:
                self._listener.join(timeout=1)
            except Exception:
                pass
            return not self._listener.is_alive()
        return True
