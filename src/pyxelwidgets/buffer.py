"""
Frame buffers are ``uint8`` arrays of shape ``(width, height, 4)`` holding
straight (non-premultiplied) RGBA, indexed as ``buffer[x, y]``.
Any :class:`~pyxelwidgets.color.Color` can be assigned to a buffer cell or slice.
"""

import numpy

import pyxelwidgets.color

def new(width: int, height: int, color: pyxelwidgets.color.Color = None) -> numpy.ndarray:
    """Create a buffer filled with ``color`` (transparent by default)."""
    buffer = numpy.zeros((width, height, 4), dtype = numpy.uint8)
    if color is not None:
        buffer[:] = color
    return buffer

def to_buffer(data) -> numpy.ndarray:
    """Convert an RGBA array, or a 2-d array/list of Colors, to a buffer."""
    if isinstance(data, numpy.ndarray) and data.dtype != object:
        if data.ndim != 3 or data.shape[2] != 4:
            raise ValueError(f'buffer must have shape (width, height, 4), got {data.shape}')
        return data.astype(numpy.uint8, copy = True)
    # Not numpy.asarray: it would expand each Color through __array__
    columns = [list(column) for column in data]
    buffer = new(len(columns), len(columns[0]))
    for x, column in enumerate(columns):
        for y, pixel in enumerate(column):
            buffer[x, y] = pixel
    return buffer

def composite(dst: numpy.ndarray, src: numpy.ndarray) -> None:
    """Draw ``src`` over ``dst`` in place using alpha ("over") blending."""
    src_alpha = src[..., 3]
    if src_alpha.min() == 255:
        dst[:] = src
        return
    if src_alpha.max() == 0:
        return
    sa = src_alpha[..., None] / 255.0
    da = dst[..., 3:].astype(numpy.float64) / 255.0
    out_alpha = sa + da * (1.0 - sa)
    rgb = src[..., :3] * sa + dst[..., :3] * da * (1.0 - sa)
    rgb = numpy.divide(rgb, out_alpha, out = numpy.zeros_like(rgb), where = out_alpha > 0)
    dst[..., :3] = numpy.rint(rgb)
    dst[..., 3] = numpy.rint(out_alpha[..., 0] * 255.0)
