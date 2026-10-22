from queue import Empty
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from system_viewer import SystemWideViewer, ViewerUnavailable, key_identity, listener_factory


class FakeListener:
    def __init__(self, **callbacks):
        self.callbacks = callbacks
        self.running = False
        self.ident = None
        self.alive = False

    def start(self):
        self.alive = self.running = True
        self.ident = 1

    def is_alive(self):
        return self.alive

    def stop(self):
        self.alive = self.running = False

    def join(self, timeout=None):
        pass


def letter(char="a", vk=65):
    return SimpleNamespace(char=char, vk=vk)


class SystemViewerTests(unittest.TestCase):
    def test_initial_disabled_duplicate_start_and_fresh_listener(self):
        viewer = SystemWideViewer(FakeListener)
        self.assertEqual(viewer.phase, "stopped")
        self.assertIsNone(viewer._listener)
        viewer.start()
        original = viewer._listener
        viewer.start()
        self.assertIs(viewer._listener, original)
        viewer.poll()
        self.assertEqual(viewer.phase, "active")
        viewer.stop()
        viewer.start()
        self.assertIsNot(viewer._listener, original)
        self.assertFalse(original.callbacks["on_press"](letter()))
        self.assertIsNone(viewer.poll())
        self.assertTrue(viewer.close())

    def test_threaded_callbacks_coalesce_no_history_and_stop_gates(self):
        viewer = SystemWideViewer(FakeListener)
        viewer.start()
        callbacks = viewer._listener.callbacks
        def burst():
            for _ in range(10000):
                callbacks["on_press"](letter())
                callbacks["on_release"](letter())
        worker = Thread(target=burst)
        worker.start()
        worker.join()
        self.assertEqual(viewer._queue.qsize(), 1)
        self.assertEqual(viewer._held, {})
        snapshot = viewer.poll()
        self.assertEqual(snapshot.combination, "a")
        self.assertEqual(snapshot.held, ())
        self.assertIsNotNone(snapshot.expires_at)
        self.assertFalse(hasattr(viewer, "history"))
        callbacks["on_press"](letter())
        viewer.stop()
        self.assertFalse(callbacks["on_release"](letter()))
        self.assertEqual(viewer._queue.qsize(), 0)
        self.assertEqual(viewer._held, {})

    def test_modifiers_release_identity_and_autorepeat(self):
        viewer = SystemWideViewer(FakeListener)
        viewer.start()
        press = viewer._listener.callbacks["on_press"]
        release = viewer._listener.callbacks["on_release"]
        ctrl = SimpleNamespace(name="ctrl_l")
        shift = SimpleNamespace(name="shift_l")
        press(ctrl)
        press(shift)
        for _ in range(20):
            press(letter("A"))
        self.assertEqual(viewer.poll().combination, "Ctrl + Shift + A")
        release(shift)
        release(letter("a"))
        self.assertEqual(viewer.poll().combination, "Ctrl")
        release(ctrl)
        self.assertEqual(viewer.poll().held, ())
        self.assertEqual(key_identity(letter("\x01"))[1], "A")
        viewer.close()

    def test_failures_dead_listener_and_shutdown(self):
        def unavailable(**kwargs):
            raise ViewerUnavailable("Missing test dependency")
        viewer = SystemWideViewer(unavailable)
        with self.assertRaisesRegex(ViewerUnavailable, "Missing test dependency"):
            viewer.start()
        self.assertEqual(viewer.phase, "error")
        self.assertTrue(viewer.close())
        viewer = SystemWideViewer(FakeListener)
        viewer.start()
        viewer._listener.alive = False
        viewer.poll()
        self.assertEqual(viewer.phase, "error")
        self.assertTrue(viewer._cancel.is_set())

    def test_unsupported_environments(self):
        with patch("system_viewer.sys.platform", "linux"), patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
            with self.assertRaisesRegex(ViewerUnavailable, "Wayland"):
                listener_factory()
        with patch("system_viewer.sys.platform", "linux"), patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ViewerUnavailable, "X11"):
                listener_factory()
        with patch("system_viewer.sys.platform", "other"):
            with self.assertRaisesRegex(ViewerUnavailable, "unsupported"):
                listener_factory()

    def test_typing_preview_preserves_order_case_until_clear(self):
        viewer = SystemWideViewer(FakeListener)
        viewer.start()
        press = viewer._listener.callbacks["on_press"]
        release = viewer._listener.callbacks["on_release"]
        for char in "oiu":
            press(letter(char, ord(char)))
            release(letter(char, ord(char)))
        snapshot = viewer.poll()
        self.assertEqual(snapshot.preview, "oiu")
        press(letter("A"))
        release(letter("A"))
        press(SimpleNamespace(name="space"))
        release(SimpleNamespace(name="space"))
        press(letter("!", 49))
        release(letter("!", 49))
        self.assertEqual(viewer.poll().preview, "oiuA !")
        press(SimpleNamespace(name="backspace"))
        release(SimpleNamespace(name="backspace"))
        snapshot = viewer.poll()
        self.assertEqual(snapshot.preview, "oiuA ")
        with patch("system_viewer.time.monotonic", return_value=10**12):
            viewer.poll()
            self.assertEqual(viewer.preview, "oiuA ")
            press(letter("z", 90))
            self.assertEqual(viewer.poll().preview, "oiuA z")
        viewer.stop()
        self.assertEqual(viewer.preview, "oiuA z")
        viewer.start()
        viewer._listener.callbacks["on_press"](letter("b", 66))
        self.assertEqual(viewer.preview, "oiuA zb")
        viewer.clear()
        self.assertEqual(viewer.preview, "")
        viewer.close()

    def test_preview_is_bounded_and_does_not_append_shortcuts(self):
        viewer = SystemWideViewer(FakeListener)
        viewer.start()
        press = viewer._listener.callbacks["on_press"]
        release = viewer._listener.callbacks["on_release"]
        for _ in range(100):
            press(letter())
            release(letter())
        self.assertEqual(viewer.poll().preview, "a" * 48)
        press(SimpleNamespace(name="ctrl_l"))
        press(letter("c", 67))
        self.assertEqual(viewer.poll().preview, "a" * 48)
        viewer.close()


if __name__ == "__main__":
    unittest.main()
