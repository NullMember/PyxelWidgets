"""The browser grid: its page, the WebSocket protocol, and a real browser."""

import base64
import json
import os
import socket
import struct
import urllib.request

import pytest

from pyxelwidgets import Button, Colors, PadPressed, PadReleased, Surface
from pyxelwidgets.devices.web import WebGrid


@pytest.fixture
def grid():
    grid = WebGrid(columns = 4, rows = 2, port = 0, host = '127.0.0.1', title = 'Test grid')
    grid.connect()
    yield grid
    grid.close()


class Browser:
    """A minimal WebSocket client, like the page."""

    def __init__(self, grid):
        self.socket = socket.create_connection(('127.0.0.1', grid.server.server_address[1]), timeout = 5)
        key = base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall((f'GET /ws HTTP/1.1\r\nHost: test\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                             f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        self.stream = self.socket.makefile('rb')
        response = b''
        while not response.endswith(b'\r\n\r\n'):
            response += self.stream.read(1)
        assert b'101' in response.split(b'\r\n')[0]

    def receive(self):
        head = self.stream.read(2)
        length = head[1] & 0x7F
        if length == 126:
            length = struct.unpack('>H', self.stream.read(2))[0]
        elif length == 127:
            length = struct.unpack('>Q', self.stream.read(8))[0]
        return json.loads(self.stream.read(length))

    def send(self, data):
        payload, mask = json.dumps(data).encode(), os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(bytes([0x81, 0x80 | len(payload)]) + mask + masked)

    def close(self):
        # The stream holds the socket open too
        self.stream.close()
        self.socket.close()


def test_page_is_served(grid):
    page = urllib.request.urlopen(grid.url).read().decode()
    assert '<title>Test grid</title>' in page and 'WebSocket' in page
    assert grid.url.startswith('http://127.0.0.1:')


def test_pixels_and_presses(grid):
    events = []
    grid.on(PadPressed, events.append)
    grid.on(PadReleased, events.append)
    browser = Browser(grid)
    first = browser.receive()
    assert first['size'] == [4, 2] and len(first['pixels']) == 8
    surface = Surface(4, 2)
    surface.add_device(grid)
    surface.add(Button(1, 1, 1, 1, value = 1.0, active_color = Colors.Red))
    surface.update()
    assert [1, 1, '#ff0000'] in browser.receive()['pixels']
    browser.send({'x': 2, 'y': 0, 'v': 1})
    browser.send({'x': 3, 'y': 1, 'v': 0.5})
    browser.send({'x': 3, 'y': 1, 'v': 0})
    browser.send({'x': 9, 'y': 0, 'v': 1})       # outside the grid: ignored
    browser.close()
    # The pad still held when the page closed is released
    import time
    end = time.monotonic() + 5
    while len(events) < 4 and time.monotonic() < end:
        time.sleep(0.01)
    assert [(type(e), e.x, e.y, e.velocity) for e in events] == [
        (PadPressed, 2, 0, 1.0), (PadPressed, 3, 1, 0.5), (PadReleased, 3, 1, 0.0), (PadReleased, 2, 0, 0.0)]


def test_in_a_browser(grid):
    playwright = pytest.importorskip('playwright.sync_api')
    events = []
    grid.on(PadPressed, events.append)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport = {'width': 600, 'height': 400}, has_touch = True)
        page.goto(grid.url)
        page.wait_for_selector('.pad[data-key="0,0"]')
        grid.show(__import__('pyxelwidgets.buffer', fromlist = ['new']).new(4, 2, Colors.Lime))
        page.wait_for_function('document.querySelector(\'.pad[data-key="3,1"]\').style.background.includes("0, 255, 0")')
        page.click('.pad[data-key="1,1"]')
        browser.close()
    assert [(e.x, e.y) for e in events] == [(1, 1)]


def test_fullscreen(grid):
    manifest = json.loads(urllib.request.urlopen(grid.url + 'manifest.json').read())
    assert manifest['display'] == 'fullscreen' and manifest['name'] == 'Test grid'
    playwright = pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport = {'width': 600, 'height': 400})
        page.goto(grid.url)
        page.wait_for_selector('.pad')
        assert page.is_visible('#fullscreen')
        page.click('#fullscreen')
        page.wait_for_function('!!document.fullscreenElement')
        assert page.is_hidden('#fullscreen')
        browser.close()
