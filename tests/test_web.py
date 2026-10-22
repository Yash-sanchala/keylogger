"""Real loopback HTTP/WS and console integration; fake keyboard listener only."""

import asyncio
import time
import unittest

try:
    from aiohttp import ClientSession, WSServerHandshakeError
except ImportError:
    raise unittest.SkipTest("Install requirements.txt to run local web tests")

from system_viewer import SystemWideViewer
from test_system_viewer import FakeListener, letter
from console_main import ConsoleController
from web_server import BrowserBridge, LocalWebServer


class WebTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = LocalWebServer(BrowserBridge(), port=0)
        self.app = ConsoleController(self.server.bridge, SystemWideViewer(FakeListener))
        self.server.start()
        self.client = ClientSession()
        deadline = time.monotonic() + 5
        while not self.server.ready.is_set() and time.monotonic() < deadline:
            await self.pump(0.05)
        self.assertTrue(self.server.ready.is_set())
        self.assertEqual(self.server.failed, "")
        self.sockets = []

    async def asyncTearDown(self):
        for ws in self.sockets:
            await ws.close()
        await self.client.close()
        self.app.close()
        self.server.close()
        self.assertFalse(self.server.thread.is_alive())

    async def pump(self, seconds=0.2):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.app.tick()
            await asyncio.sleep(0.01)

    async def connect(self):
        # Browser clients offer compression; the server deliberately declines it.
        ws = await self.client.ws_connect(f"{self.server.origin}/live?token={self.server.token}", origin=self.server.origin, compress=15)
        self.assertEqual(ws.compress, 0)
        self.sockets.append(ws)
        await self.pump()
        return ws

    async def state_matching(self, ws, predicate):
        async def receive_matching():
            while True:
                state = await ws.receive_json()
                if predicate(state):
                    return state
        return await asyncio.wait_for(receive_matching(), timeout=3)

    async def test_assets_and_local_connection_checks(self):
        self.assertEqual(self.server.browser_url, self.server.origin + "/")
        response = await self.client.post(self.server.origin + "/session", headers={
            "Origin": self.server.origin, "X-Keyboard-Lab": "viewer", "Sec-Fetch-Site": "same-origin"})
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["token"], self.server.token)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        for headers in ({}, {"Origin": "https://outside.example", "X-Keyboard-Lab": "viewer"},
                        {"Origin": self.server.origin},
                        {"Origin": self.server.origin, "X-Keyboard-Lab": "viewer", "Sec-Fetch-Site": "cross-site"}):
            response = await self.client.post(self.server.origin + "/session", headers=headers)
            self.assertEqual(response.status, 403)
        for path in ("/", "/app.js", "/style.css"):
            response = await self.client.get(self.server.origin + path)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            self.assertTrue(await response.read())
        response = await self.client.get(self.server.origin, headers={"Host": "outside.example"})
        self.assertEqual(response.status, 403)
        for query, origin in (("bad-token", self.server.origin), (self.server.token, "https://outside.example")):
            with self.assertRaises(WSServerHandshakeError) as error:
                await self.client.ws_connect(f"{self.server.origin}/live?token={query}", origin=origin)
            self.assertEqual(error.exception.status, 403)
        self.assertFalse(self.app.viewer.enabled)

    async def test_live_preview_start_stop_clear_and_no_duplicate_listener(self):
        ws = await self.connect()
        initial = await self.state_matching(ws, lambda s: s["phase"] == "stopped")
        self.assertEqual(initial["preview"], "")
        await ws.send_json({"action": "start"})
        await self.pump()
        await self.state_matching(ws, lambda s: s["phase"] == "active")
        listener = self.app.viewer._listener
        await ws.send_json({"action": "start"})
        await self.pump()
        self.assertIs(self.app.viewer._listener, listener)
        for char in "oiu":
            listener.callbacks["on_press"](letter(char, ord(char)))
            listener.callbacks["on_release"](letter(char, ord(char)))
        await self.pump()
        state = await self.state_matching(ws, lambda s: s["preview"] == "oiu")
        self.assertNotIn("history", state)
        self.assertEqual(self.app.viewer.preview, "oiu")
        await ws.send_json({"action": "stop"})
        await self.pump()
        stopped = await self.state_matching(ws, lambda s: s["phase"] == "stopped")
        self.assertEqual(stopped["preview"], "oiu")
        self.assertFalse(listener.callbacks["on_press"](letter()))
        await ws.send_json({"action": "clear"})
        await self.pump()
        await self.state_matching(ws, lambda s: s["preview"] == "")
        self.assertEqual(self.app.viewer.preview, "")

    async def test_disconnect_stops_and_reconnect_does_not_resume(self):
        ws = await self.connect()
        await ws.send_json({"action": "start"})
        await self.pump()
        self.assertTrue(self.app.viewer.enabled)
        await ws.close()
        await self.pump()
        self.assertFalse(self.app.viewer.enabled)
        other = await self.connect()
        await self.state_matching(other, lambda s: s["phase"] == "stopped")
        self.assertFalse(self.app.viewer.enabled)
        await other.send_json({"action": "start"})
        await self.pump()
        self.assertTrue(self.app.viewer.enabled)

    async def test_second_tab_and_invalid_command(self):
        ws = await self.connect()
        with self.assertRaises(WSServerHandshakeError) as error:
            await self.connect()
        self.assertEqual(error.exception.status, 409)
        await ws.send_json({"action": "start"})
        await self.pump()
        self.assertTrue(self.app.viewer.enabled)
        await ws.send_json({"action": "not-a-command"})
        # Drain frames so the aiohttp test client completes the close handshake.
        while not ws.closed:
            await asyncio.wait_for(ws.receive(), timeout=3)
        await self.pump()
        self.assertFalse(self.app.viewer.enabled)


class BridgeTests(unittest.TestCase):
    def test_disconnect_drops_pending_start_and_old_owner(self):
        bridge = BrowserBridge()
        self.assertTrue(bridge.connect("first"))
        bridge.command("first", "start")
        bridge.disconnect("first")
        self.assertTrue(bridge.connect("second"))
        self.assertFalse(bridge.command("first", "start"))
        owner, epoch, heartbeat, commands = bridge.take_commands()
        self.assertEqual(owner, "second")
        self.assertEqual(epoch, 3)
        self.assertEqual(commands, [])

    def test_stop_takes_priority_over_a_full_queue(self):
        bridge = BrowserBridge()
        bridge.connect("owner")
        for _ in range(32):
            self.assertTrue(bridge.command("owner", "start"))
        self.assertFalse(bridge.command("owner", "start"))
        self.assertTrue(bridge.command("owner", "stop"))
        self.assertEqual(bridge.take_commands()[-1], ["stop"])


if __name__ == "__main__":
    unittest.main()
