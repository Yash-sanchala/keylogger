"""Check the packaged website without enabling keyboard or camera capture."""
import asyncio
from pathlib import Path
import signal
import subprocess
import time
from urllib.request import urlopen

from aiohttp import ClientSession


async def verify(origin):
    async with ClientSession() as client:
        async with client.post(origin + '/session', headers={
                'Origin': origin, 'X-Keyboard-Lab': 'viewer'}) as response:
            assert response.status == 200
            token = (await response.json())['token']
        async with client.ws_connect(origin + '/live?token=' + token, origin=origin) as ws:
            state = await asyncio.wait_for(ws.receive_json(), 5)
            assert state['phase'] == 'stopped'
            assert state['preview'] == ''


if __name__ == '__main__':
    executable = Path(__file__).resolve().parents[1] / 'KeyboardMonitorLab.exe'
    origin = 'http://127.0.0.1:18764'
    process = subprocess.Popen([str(executable), '--port', '18764'],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, text=True,
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        deadline = time.monotonic() + 20
        while True:
            if process.poll() is not None:
                raise AssertionError('Executable exited early:\n' + process.stdout.read())
            try:
                with urlopen(origin, timeout=1) as response:
                    html = response.read()
                    assert b'id="start"' in html
                    assert b'camera' not in html.lower()
                    assert b'microphone' not in html.lower()
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise AssertionError('Packaged website did not become ready')
                time.sleep(0.2)
        for asset in ['/app.js', '/style.css']:
            with urlopen(origin + asset, timeout=2) as response:
                assert response.status == 200
        asyncio.run(verify(origin))
        process.send_signal(signal.CTRL_BREAK_EVENT)
        assert process.wait(timeout=5) == 0
        print('PASS: packaged website, keyboard-only assets, stopped keyboard state, clean shutdown')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
