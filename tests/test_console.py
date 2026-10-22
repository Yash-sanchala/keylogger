import unittest
from console_main import ConsoleController
from system_viewer import SystemWideViewer
from web_server import BrowserBridge
from test_system_viewer import FakeListener, letter


class ConsoleTests(unittest.TestCase):
    def test_start_preview_stop_clear_disconnect_and_cleanup(self):
        bridge = BrowserBridge()
        app = ConsoleController(bridge, SystemWideViewer(FakeListener))
        try:
            self.assertEqual(app.tick()["phase"], "stopped")
            bridge.connect("browser")
            bridge.command("browser", "start")
            app.tick()
            listener = app.viewer._listener
            bridge.command("browser", "start")
            app.tick()
            self.assertIs(app.viewer._listener, listener)
            for char in "oiu":
                listener.callbacks["on_press"](letter(char, ord(char)))
                listener.callbacks["on_release"](letter(char, ord(char)))
            self.assertEqual(app.tick()["preview"], "oiu")
            bridge.command("browser", "stop")
            self.assertEqual(app.tick()["preview"], "oiu")
            self.assertFalse(app.viewer.enabled)
            bridge.command("browser", "clear")
            self.assertEqual(app.tick()["preview"], "")
            bridge.command("browser", "start")
            app.tick()
            bridge.disconnect("browser")
            app.tick()
            self.assertFalse(app.viewer.enabled)
            bridge.connect("new")
            app.tick()
            self.assertFalse(app.viewer.enabled)
        finally:
            app.close()
