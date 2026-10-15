"""
Draws the application icon (a 4x4 grid of lit pads) at any size with numpy and
writes PNG, ICO (Windows) and ICNS (macOS) files with the standard library only.

    python packaging/icon.py               # the designer's favicon (designer/static/icon.png)
    python packaging/icon.py build/icon    # also icon.icns / icon.ico / icon.png there (build.py does this)
"""

import pathlib
import struct
import sys
import zlib

import numpy

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAVICON = ROOT / 'src' / 'pyxelwidgets' / 'designer' / 'static' / 'icon.png'

BACKGROUND = (18, 20, 24)
# Rows from the top: a little scene of a layout (a fader, steps, a playing column)
PADS = [
    ['#2ee6a6', '#ffb020', '#20242c', '#ff4d6d'],
    ['#2ee6a6', '#20242c', '#4da3ff', '#20242c'],
    ['#2ee6a6', '#4da3ff', '#20242c', '#ffb020'],
    ['#2ee6a6', '#20242c', '#ff4d6d', '#4da3ff'],
]

def _rounded(size: int, x0: float, y0: float, x1: float, y1: float, radius: float) -> numpy.ndarray:
    """Coverage (0-1) of a rounded rectangle on a ``size`` square, 4x4 supersampled."""
    samples = (numpy.arange(size * 4) + 0.5) / 4
    x = samples[None, :]
    y = samples[:, None]
    dx = numpy.maximum(numpy.maximum(x0 + radius - x, x - (x1 - radius)), 0)
    dy = numpy.maximum(numpy.maximum(y0 + radius - y, y - (y1 - radius)), 0)
    inside = (dx * dx + dy * dy <= radius * radius) & (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    return inside.reshape(size, 4, size, 4).mean(axis = (1, 3))

def draw(size: int) -> numpy.ndarray:
    """The icon as a ``uint8 (size, size, 4)`` RGBA image, rows from the top."""
    image = numpy.zeros((size, size, 4), dtype = float)
    # macOS-style margins: the tile fills about 80 % of the canvas
    margin = size * 0.1
    tile = _rounded(size, margin, margin, size - margin, size - margin, size * 0.18)
    image[..., :3] = BACKGROUND
    image[..., 3] = tile * 255
    inner = size - 2 * margin
    edge = inner * 0.1
    gap = inner * 0.045
    pad = (inner - 2 * edge - gap * 3) / 4
    for row, colors in enumerate(PADS):
        for column, color in enumerate(colors):
            x0 = margin + edge + column * (pad + gap)
            y0 = margin + edge + row * (pad + gap)
            coverage = _rounded(size, x0, y0, x0 + pad, y0 + pad, pad * 0.18)[..., None]
            rgb = numpy.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], dtype = float)
            image[..., :3] = image[..., :3] * (1 - coverage) + rgb * coverage
    return numpy.round(image).astype(numpy.uint8)

def png(image: numpy.ndarray) -> bytes:
    height, width = image.shape[:2]
    raw = b''.join(b'\0' + image[row].tobytes() for row in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

def ico(sizes = (16, 24, 32, 48, 64, 128, 256)) -> bytes:
    """Windows icon with PNG entries (Windows Vista and later)."""
    images = [png(draw(size)) for size in sizes]
    header = struct.pack('<HHH', 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = b''
    for size, data in zip(sizes, images):
        entries += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b''.join(images)

def icns() -> bytes:
    """macOS icon with PNG entries."""
    kinds = [(b'icp4', 16), (b'icp5', 32), (b'icp6', 64), (b'ic07', 128), (b'ic08', 256), (b'ic09', 512), (b'ic10', 1024),
             (b'ic11', 32), (b'ic12', 64), (b'ic13', 256), (b'ic14', 512)]
    body = b''
    for kind, size in kinds:
        data = png(draw(size))
        body += kind + struct.pack('>I', len(data) + 8) + data
    return b'icns' + struct.pack('>I', len(body) + 8) + body

def main(argv = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    FAVICON.write_bytes(png(draw(64)))
    if argv:
        folder = pathlib.Path(argv[0])
        folder.mkdir(parents = True, exist_ok = True)
        (folder / 'icon.png').write_bytes(png(draw(512)))
        (folder / 'icon.ico').write_bytes(ico())
        (folder / 'icon.icns').write_bytes(icns())

if __name__ == '__main__':
    main()
