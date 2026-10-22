"""Loopback-only HTTP/WebSocket service. Never calls Tk or starts a listener."""

import asyncio
from collections import deque
from contextlib import suppress
from pathlib import Path
import secrets
import threading
import time


class BrowserBridge:
    """Small thread-safe control mailbox and one current display snapshot."""

    def __init__(self):
        self.lock = threading.Lock()
        self.owner = None
        self.epoch = 0
        self.last_heartbeat = 0.0
        self.commands = deque()
        self.state = {"phase": "stopped", "key": "", "held": [], "preview": "", "error": ""}

    def connect(self, owner):
        with self.lock:
            if self.owner is not None:
                return False
            self.owner = owner
            self.epoch += 1
            self.last_heartbeat = time.monotonic()
            self.commands.clear()
            return True

    def disconnect(self, owner):
        with self.lock:
            if self.owner == owner:
                self.owner = None
                self.epoch += 1
                self.commands.clear()

    def heartbeat(self, owner):
        with self.lock:
            if self.owner == owner:
                self.last_heartbeat = time.monotonic()

    def command(self, owner, action):
        if action not in ("start", "stop", "clear"):
            return False
        with self.lock:
            if self.owner != owner:
                return False
            if action == "stop":
                self.commands.clear()
            if len(self.commands) >= 32:
                return False
            self.commands.append(action)
            return True

    def take_commands(self):
        with self.lock:
            commands = list(self.commands)
            self.commands.clear()
            return self.owner, self.epoch, self.last_heartbeat, commands

    def discard_commands(self):
        with self.lock:
            self.commands.clear()

    def publish(self, state):
        with self.lock:
            self.state = dict(state)

    def snapshot(self):
        with self.lock:
            return dict(self.state)


def create_web_app(bridge, token, origin):
    from aiohttp import WSMsgType, web

    assets = Path(__file__).with_name("web")
    routes = {
        "/": ("index.html", "text/html"),
        "/app.js": ("app.js", "application/javascript"),
        "/style.css": ("style.css", "text/css"),
    }

    @web.middleware
    async def local_only(request, handler):
        # Explicit Host + Origin checks reject DNS rebinding and cross-site WS.
        if request.host != origin().removeprefix("http://"):
            raise web.HTTPForbidden(text="Use the address opened by the local service.")
        response = await handler(request)
        if not isinstance(response, web.WebSocketResponse):
            response.headers.update({
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            })
        return response

    async def asset(request):
        name, mime = routes[request.path]
        return web.Response(body=(assets / name).read_bytes(), content_type=mime)

    async def session(request):
        # Only this origin's page can fetch the per-run capability. A foreign
        # page's custom-header request needs CORS preflight, which we deny.
        if (request.headers.get("Origin") != origin()
                or request.headers.get("X-Keyboard-Lab") != "viewer"
                or request.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin"):
            raise web.HTTPForbidden(text="Open the local Keyboard Monitor Lab page.")
        return web.json_response({"token": token})

    async def websocket(request):
        if request.headers.get("Origin") != origin():
            raise web.HTTPForbidden(text="This page must be opened from the local service.")
        if not secrets.compare_digest(request.query.get("token", ""), token):
            raise web.HTTPForbidden(text="Open the viewer from http://127.0.0.1:8000/.")
        owner = secrets.token_hex(16)
        if not bridge.connect(owner):
            raise web.HTTPConflict(text="Another viewer tab is connected. Close it before reconnecting.")
        # These tiny loopback messages do not benefit from compression. Keep
        # browser commands independent of permessage-deflate negotiation.
        ws = web.WebSocketResponse(heartbeat=1.0, max_msg_size=1024, timeout=1.0, compress=False)
        sender = None

        async def send_states():
            previous = None
            while not ws.closed:
                bridge.heartbeat(owner)
                state = bridge.snapshot()
                if state != previous:
                    await ws.send_json({"type": "state", **state})
                    previous = state
                await asyncio.sleep(0.05)

        try:
            await ws.prepare(request)
            sender = asyncio.create_task(send_states())
            async for message in ws:
                if message.type == WSMsgType.TEXT:
                    try:
                        body = message.json()
                    except (ValueError, TypeError):
                        await ws.close(code=1008, message=b"Invalid command")
                        break
                    if not isinstance(body, dict) or not bridge.command(owner, body.get("action")):
                        await ws.close(code=1008, message=b"Invalid command or command queue full")
                        break
                elif message.type == WSMsgType.ERROR:
                    break
        finally:
            bridge.disconnect(owner)
            if sender:
                sender.cancel()
                with suppress(asyncio.CancelledError, ConnectionError):
                    await sender
        return ws

    app = web.Application(middlewares=[local_only], client_max_size=1024)
    app.add_routes([web.get(path, asset) for path in routes])
    app.router.add_get("/live", websocket)
    app.router.add_post("/session", session)
    return app


class LocalWebServer:
    def __init__(self, bridge, port=8000):
        self.bridge = bridge
        self.port = port
        self.token = secrets.token_urlsafe(32)
        self.ready = threading.Event()
        self.failed = ""
        self._closing = threading.Event()
        self.thread = None

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.port}"

    @property
    def browser_url(self):
        return f"{self.origin}/"

    def start(self):
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self._run, name="KeyboardLabWeb", daemon=True)
        self.thread.start()

    def _run(self):
        try:
            asyncio.run(self._serve())
        except ImportError:
            self.failed = "Web dependencies missing. Run: python -m pip install -r requirements.txt"
        except OSError as error:
            import traceback
            traceback.print_exc()
            self.failed = f"Local website startup failed: {error}. Port: {self.port}."
        except Exception:
            self.failed = "The local web server stopped unexpectedly. Restart the console service."
        finally:
            self.ready.set()

    async def _serve(self):
        from aiohttp import web

        runner = web.AppRunner(create_web_app(self.bridge, self.token, lambda: self.origin),
                               access_log=None, shutdown_timeout=1.0)
        await runner.setup()
        try:
            site = web.TCPSite(runner, "127.0.0.1", self.port)
            await site.start()
            self.port = runner.addresses[0][1]
            self.ready.set()
            while not self._closing.is_set():
                await asyncio.sleep(0.05)
        finally:
            await runner.cleanup()

    def close(self):
        self._closing.set()
        if self.thread:
            self.thread.join(timeout=3)
