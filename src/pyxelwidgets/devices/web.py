"""
A grid in a web browser, e.g. on a tablet or a phone::

    grid = WebGrid(columns = 8, rows = 8, port = 8800)
    grid.connect()
    print('Open', grid.url)           # on any device on the same network
    surface.add_device(grid)

Every browser that opens the page shows the grid and plays it: several
fingers at once, sliding across pads, or the mouse. The corner button goes
fullscreen; "Add to Home Screen" makes it an app that opens fullscreen.
Standard library only: a small HTTP server that talks WebSocket to the page.
"""

import base64
import hashlib
import html
import http.server
import json
import socket
import struct
import threading

import pyxelwidgets.devices

__all__ = ['WebGrid']

_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
_TEXT, _CLOSE, _PING, _PONG = 0x1, 0x8, 0x9, 0xA

def _frame(opcode: int, payload: bytes) -> bytes:
    """A WebSocket frame from the server (unmasked, not fragmented)."""
    length = len(payload)
    if length < 126:
        head = bytes([0x80 | opcode, length])
    elif length < 1 << 16:
        head = bytes([0x80 | opcode, 126]) + struct.pack('>H', length)
    else:
        head = bytes([0x80 | opcode, 127]) + struct.pack('>Q', length)
    return head + payload

def _read_frame(stream) -> tuple | None:
    """(opcode, payload) of the next frame from a browser, or None when the connection ended."""
    head = stream.read(2)
    if len(head) < 2:
        return None
    opcode, length = head[0] & 0x0F, head[1] & 0x7F
    if length == 126:
        length = struct.unpack('>H', stream.read(2))[0]
    elif length == 127:
        length = struct.unpack('>Q', stream.read(8))[0]
    mask = stream.read(4) if head[1] & 0x80 else b''
    payload = stream.read(length)
    if len(payload) < length:
        return None
    if mask:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload

def _address() -> str:
    """This computer's address on the network (no traffic is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('10.255.255.255', 1))
            return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'

class _Client:
    """One browser: writes are serialized, held pads are released when it leaves."""

    def __init__(self, connection) -> None:
        self.connection = connection
        self.lock = threading.Lock()
        self.held = set()

    def send(self, data: dict) -> None:
        frame = _frame(_TEXT, json.dumps(data, separators = (',', ':')).encode())
        with self.lock:
            try:
                self.connection.sendall(frame)
            except OSError:
                pass

    def close(self) -> None:
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

class WebGrid(pyxelwidgets.devices.Device):
    """
    A ``columns`` x ``rows`` grid shown in web browsers, served on ``port``
    (``url`` after ``connect``). Pads are pressed by touch or mouse; pen
    pressure is the velocity, otherwise it is 1.0.
    """

    vendor = 'PyxelWidgets'
    model = 'Web Grid'
    grid = (8, 8)
    color_model = pyxelwidgets.devices.RGB(bits = 8, gamma = False)

    def __init__(self, *, columns: int = 8, rows: int = 8, port: int = 8800, host: str = '0.0.0.0', title: str = 'PyxelWidgets', **kwargs):
        """
        columns, rows: int = 8, optional
            The grid's size.
        port: int = 8800, optional
            The HTTP port browsers open (0: any free one, see ``url``).
        host: str = '0.0.0.0', optional
            The address to listen on; '127.0.0.1' for this computer only.
        title: str = 'PyxelWidgets', optional
            The page title.
        """
        super().__init__(width = columns, height = rows, **kwargs)
        self.port = port
        self.host = host
        self.title = title
        self.server = None
        self.clients = []
        self._clients_lock = threading.Lock()

    @property
    def url(self) -> str | None:
        """The page's address for other devices on the network, while connected."""
        server = self.server
        if server is None:
            return None
        return f'http://{self._address}:{server.server_address[1]}/'

    def connect(self) -> None:
        super().connect()
        device = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args) -> None:
                pass

            def do_GET(self) -> None:
                if self.path.split('?')[0] == '/ws' and self.headers.get('Upgrade', '').lower() == 'websocket':
                    device._serve_socket(self)
                elif self.path.split('?')[0] in ('/', '/manifest.json'):
                    page = self.path.split('?')[0] == '/'
                    if page:
                        body = _PAGE.replace('{{title}}', html.escape(device.title)).encode()
                    else:
                        # Opened from the home screen: fullscreen, landscape or portrait
                        body = json.dumps({'name': device.title, 'short_name': device.title, 'start_url': '/',
                                           'display': 'fullscreen', 'background_color': '#111111', 'theme_color': '#111111'}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8' if page else 'application/manifest+json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_error(404)

        self.server = http.server.ThreadingHTTPServer((self.host, self.port), Handler)
        self._address = _address() if self.host in ('0.0.0.0', '') else self.host
        self.server.daemon_threads = True
        threading.Thread(target = self.server.serve_forever, name = f'{self.name}_web', daemon = True).start()

    def disconnect(self) -> None:
        server, self.server = self.server, None
        if server is not None:
            server.shutdown()
            server.server_close()
        with self._clients_lock:
            clients, self.clients = self.clients, []
        for client in clients:
            client.close()
        super().disconnect()

    def send_pixels(self, pixels: list) -> None:
        if pixels:
            self._broadcast({'pixels': [[x, y, '#%02x%02x%02x' % tuple(value)] for x, y, value in pixels]})

    def _broadcast(self, data: dict) -> None:
        with self._clients_lock:
            clients = list(self.clients)
        for client in clients:
            client.send(data)

    def _everything(self) -> dict:
        """What the grid shows, for a browser that just opened it."""
        values = self.color_model.convert(self.buffer.reshape(-1, 4))
        height = self.rect.h
        pixels = [[index // height, index % height, '#%02x%02x%02x' % tuple(value)] for index, value in enumerate(values)]
        return {'size': [self.rect.w, self.rect.h], 'title': self.title, 'pixels': pixels}

    def _serve_socket(self, request) -> None:
        key = request.headers.get('Sec-WebSocket-Key', '')
        accept = base64.b64encode(hashlib.sha1((key + _GUID).encode()).digest()).decode()
        request.send_response(101, 'Switching Protocols')
        request.send_header('Upgrade', 'websocket')
        request.send_header('Connection', 'Upgrade')
        request.send_header('Sec-WebSocket-Accept', accept)
        request.end_headers()
        request.wfile.flush()
        client = _Client(request.connection)
        # Registered first, so no update is missed; updates wait for the client's lock until it has everything
        with client.lock:
            with self._clients_lock:
                self.clients.append(client)
            frame = _frame(_TEXT, json.dumps(self._everything(), separators = (',', ':')).encode())
            request.connection.sendall(frame)
        try:
            while True:
                frame = _read_frame(request.rfile)
                if frame is None or frame[0] == _CLOSE:
                    break
                opcode, payload = frame
                if opcode == _PING:
                    with client.lock:
                        client.connection.sendall(_frame(_PONG, payload))
                elif opcode == _TEXT:
                    self._input(client, payload)
        except (OSError, ValueError):
            pass
        finally:
            with self._clients_lock:
                if client in self.clients:
                    self.clients.remove(client)
            # Pads still held in a closed page are released
            for x, y in list(client.held):
                self.set_button(x, y, 0.0)
            request.close_connection = True

    def _input(self, client: _Client, payload: bytes) -> None:
        try:
            message = json.loads(payload)
            x, y, velocity = int(message['x']), int(message['y']), float(message['v'])
        except (ValueError, KeyError, TypeError):
            return
        if not (0 <= x < self.rect.w and 0 <= y < self.rect.h):
            return
        velocity = min(1.0, max(0.0, velocity))
        if velocity > 0:
            client.held.add((x, y))
        else:
            client.held.discard((x, y))
        self.set_button(x, y, velocity)

_PAGE = r'''<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#111111">
<link rel="manifest" href="/manifest.json">
<title>{{title}}</title>
<style>
  html, body { margin: 0; height: 100%; background: #111; overflow: hidden; touch-action: none;
               -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; }
  #grid { position: absolute; display: grid; gap: var(--gap); }
  .pad { border-radius: 12%; background: #000; box-shadow: inset 0 0 0 1px #2a2a2a; }
  #status { position: absolute; top: calc(6px + env(safe-area-inset-top)); left: calc(8px + env(safe-area-inset-left));
            font: 12px system-ui, sans-serif; color: #888; }
  #fullscreen { position: absolute; top: calc(6px + env(safe-area-inset-top)); right: calc(6px + env(safe-area-inset-right));
                width: 36px; height: 36px; border: 0; border-radius: 8px; background: rgba(255, 255, 255, 0.08);
                color: #aaa; font-size: 20px; line-height: 36px; padding: 0; }
  #fullscreen[hidden] { display: none; }
  #back { position: absolute; top: calc(6px + env(safe-area-inset-top)); left: calc(6px + env(safe-area-inset-left));
          height: 36px; border: 0; border-radius: 8px; background: rgba(255, 255, 255, 0.08); color: #aaa;
          font: 14px system-ui, sans-serif; padding: 0 12px; }
  #back[hidden] { display: none; }
  #back:not([hidden]) ~ #status { left: calc(120px + env(safe-area-inset-left)); top: calc(16px + env(safe-area-inset-top)); }
</style>
</head><body>
<div id="grid"></div><button id="back" hidden>◀ Designer</button><div id="status">connecting…</div>
<button id="fullscreen" title="Fullscreen" aria-label="Fullscreen" hidden>⛶</button>
<script>
const grid = document.getElementById('grid'), status = document.getElementById('status');
let size = [0, 0], pads = new Map(), socket = null;
const pointers = new Map();   // pointer id → "x,y" of the pad it holds

// The screen's safe area (notches, rounded corners), from CSS
const probe = document.createElement('div');
probe.style.cssText = 'position:fixed;visibility:hidden;padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)';
document.body.appendChild(probe);

function layout() {
  const [w, h] = size;
  if (!w) return;
  const inset = getComputedStyle(probe);
  const [top, right, bottom, left] = ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'].map((key) => parseFloat(inset[key]) || 0);
  const width = innerWidth - left - right, height = innerHeight - top - bottom;
  const gapRatio = 0.12, margin = 12;
  const pad = Math.floor(Math.min((width - 2 * margin) / (w + (w - 1) * gapRatio), (height - 2 * margin) / (h + (h - 1) * gapRatio)));
  const gap = Math.max(2, Math.round(pad * gapRatio));
  grid.style.setProperty('--gap', gap + 'px');
  grid.style.gridTemplateColumns = `repeat(${w}, ${pad}px)`;
  grid.style.gridAutoRows = pad + 'px';
  grid.style.left = Math.round(left + (width - (w * pad + (w - 1) * gap)) / 2) + 'px';
  grid.style.top = Math.round(top + (height - (h * pad + (h - 1) * gap)) / 2) + 'px';
}

// Fullscreen where the browser can (not on iPhones: use "Add to Home Screen" there)
const fullscreenButton = document.getElementById('fullscreen');
const root = document.documentElement;
const requestFullscreen = root.requestFullscreen || root.webkitRequestFullscreen;
const fullscreenElement = () => document.fullscreenElement || document.webkitFullscreenElement;
// The PyxelWidgets app (Android, desktop window) is fullscreen already
const standalone = matchMedia('(display-mode: fullscreen), (display-mode: standalone)').matches || navigator.standalone
  || !!window.PyxelWidgetsHost || !!window.pywebview;
// Opened from the designer (?back=its address): a way back to it
const back = new URLSearchParams(location.search).get('back');
const backButton = document.getElementById('back');
if (back && /^https?:\/\//.test(back)) {
  backButton.hidden = false;
  // In place of this page: going back from the designer leaves the app, not returns here
  backButton.addEventListener('click', () => { location.replace(back); });
}
function showFullscreenButton() {
  fullscreenButton.hidden = !requestFullscreen || standalone || !!fullscreenElement();
}
fullscreenButton.addEventListener('click', () => {
  Promise.resolve(requestFullscreen.call(root, { navigationUI: 'hide' })).catch(() => {});
});
document.addEventListener('fullscreenchange', () => { showFullscreenButton(); layout(); });
document.addEventListener('webkitfullscreenchange', () => { showFullscreenButton(); layout(); });
showFullscreenButton();

function build(w, h) {
  size = [w, h];
  grid.textContent = '';
  pads = new Map();
  // The top row first: y counts from the bottom
  for (let y = h - 1; y >= 0; y--) for (let x = 0; x < w; x++) {
    const pad = document.createElement('div');
    pad.className = 'pad';
    pad.dataset.key = `${x},${y}`;
    grid.appendChild(pad);
    pads.set(pad.dataset.key, pad);
  }
  layout();
}

function send(key, velocity) {
  if (!socket || socket.readyState !== 1) return;
  const [x, y] = key.split(',').map(Number);
  socket.send(JSON.stringify({ x, y, v: velocity }));
}

function padAt(event) {
  const element = document.elementFromPoint(event.clientX, event.clientY);
  return element && element.classList.contains('pad') ? element.dataset.key : null;
}

function velocityOf(event) {
  return event.pointerType === 'pen' && event.pressure > 0 ? event.pressure : 1;
}

addEventListener('pointerdown', (event) => {
  const key = padAt(event);
  pointers.set(event.pointerId, key);
  if (key) send(key, velocityOf(event));
});
addEventListener('pointermove', (event) => {
  if (!pointers.has(event.pointerId)) return;
  // Sliding onto another pad releases the one before
  const key = padAt(event), before = pointers.get(event.pointerId);
  if (key === before) return;
  if (before) send(before, 0);
  if (key) send(key, velocityOf(event));
  pointers.set(event.pointerId, key);
});
function release(event) {
  const key = pointers.get(event.pointerId);
  if (key) send(key, 0);
  pointers.delete(event.pointerId);
}
addEventListener('pointerup', release);
addEventListener('pointercancel', release);
addEventListener('contextmenu', (event) => event.preventDefault());
addEventListener('resize', layout);

function open() {
  socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  socket.onopen = () => { status.textContent = ''; };
  socket.onmessage = (message) => {
    const data = JSON.parse(message.data);
    if (data.title) document.title = data.title;
    if (data.size) build(...data.size);
    for (const [x, y, color] of data.pixels || []) {
      const pad = pads.get(`${x},${y}`);
      if (pad) pad.style.background = color;
    }
  };
  socket.onclose = () => {
    status.textContent = 'disconnected, retrying…';
    setTimeout(open, 1000);
  };
}
open();
</script>
</body></html>
'''
