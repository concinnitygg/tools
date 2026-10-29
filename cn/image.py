"""Read PNG captures and score one against another.

Standard library only, so it runs anywhere; numpy speeds the scoring up when
it is importable.
"""

import struct
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}

# A channel difference at or under this many levels is noise, not a change.
NOISE_LEVELS = 2

# Rows at the top left out of a score by default: a benchmark draws its live
# stat chips there, which differ in every run.
HUD_ROWS = 96


def read_png(path):
    """`(width, height, channels, bytes)` of an 8-bit non-interlaced PNG."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != _SIGNATURE:
        raise ValueError(f"{path}: not a PNG")
    pos, idat, header = 8, [], None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        pos += 12 + length
    width, height, depth, color, _, _, interlace = header
    if depth != 8 or interlace != 0 or color not in _CHANNELS:
        raise ValueError(f"{path}: only 8-bit non-interlaced PNGs")
    channels = _CHANNELS[color]
    raw = zlib.decompress(b"".join(idat))
    return width, height, channels, unfilter(raw, width, height, channels)


def unfilter(raw, width, height, bpp):
    stride = width * bpp
    out = bytearray(stride * height)
    prev = bytearray(stride)
    for y in range(height):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)])
        if kind == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif kind == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return bytes(out)


def write_png(path, width, height, channels, pixels):
    """Write 8-bit pixels unfiltered. The inverse of `read_png`."""
    color = {v: k for k, v in _CHANNELS.items()}[channels]
    stride = width * channels
    raw = b"".join(b"\x00" + pixels[y * stride : (y + 1) * stride] for y in range(height))

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", width, height, 8, color, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(_SIGNATURE + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def score(a_path, b_path, skip_rows=HUD_ROWS):
    """`{"rmse", "changed", "max"}` between two captures below their first
    `skip_rows` rows, or None when their sizes differ. `rmse` is 0..1 over the
    color channels; `changed` counts pixels differing by more than
    `NOISE_LEVELS` in any channel."""
    wa, ha, ca, a = read_png(a_path)
    wb, hb, cb, b = read_png(b_path)
    if (wa, ha, ca) != (wb, hb, cb):
        return None
    skip = min(max(skip_rows, 0), ha) * wa * ca
    a, b = a[skip:], b[skip:]
    if not a:
        return {"rmse": 0.0, "changed": 0, "max": 0}
    color = min(ca, 3)
    try:
        import numpy as np  # noqa: PLC0415
    except ImportError:
        np = None
    if np is not None:
        x = np.frombuffer(a, np.uint8).reshape(-1, ca)[:, :color].astype(np.int32)
        y = np.frombuffer(b, np.uint8).reshape(-1, cb)[:, :color].astype(np.int32)
        d = np.abs(x - y)
        rmse = float(np.sqrt(np.mean((d / 255.0) ** 2)))
        return {"rmse": rmse, "changed": int(np.count_nonzero(d.max(axis=1) > NOISE_LEVELS)), "max": int(d.max())}
    squares, changed, most = 0, 0, 0
    for p in range(0, len(a), ca):
        worst = 0
        for c in range(color):
            diff = abs(a[p + c] - b[p + c])
            squares += diff * diff
            worst = max(worst, diff)
        changed += worst > NOISE_LEVELS
        most = max(most, worst)
    count = (len(a) // ca) * color
    return {"rmse": (squares / count) ** 0.5 / 255.0, "changed": changed, "max": most}


def describe(result):
    if result is None:
        return "sizes differ"
    return f"rmse {result['rmse']:.4f}  px>{NOISE_LEVELS} {result['changed']:8d}  max {result['max']:3d}"
