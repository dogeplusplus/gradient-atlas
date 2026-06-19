from __future__ import annotations

import json
import math
import struct
import threading
import time
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

from .dem import Surface, normalize, smooth


USER_AGENT = "DEM-Optimizer-Art/0.1 (local terrain art application)"
TERRAIN_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
_search_cache: dict[str, list[dict]] = {}
_search_lock = threading.Lock()
_last_search = 0.0


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def decode_rgb_png(data: bytes) -> tuple[int, int, bytes]:
    """Decode the 8-bit RGB non-interlaced PNGs used by Terrarium tiles."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Terrain service returned an invalid PNG")
    offset, compressed = 8, bytearray()
    width = height = 0
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", payload)
            if (depth, colour, interlace) != (8, 2, 0):
                raise ValueError("Terrain tile must be an 8-bit RGB PNG")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    raw, stride, bpp = zlib.decompress(bytes(compressed)), width * 3, 3
    output, previous, cursor = bytearray(), bytearray(stride), 0
    for _ in range(height):
        filter_type, cursor = raw[cursor], cursor + 1
        scan = bytearray(raw[cursor:cursor + stride]); cursor += stride
        for i, value in enumerate(scan):
            left = scan[i - bpp] if i >= bpp else 0
            above = previous[i]
            upper_left = previous[i - bpp] if i >= bpp else 0
            if filter_type == 1: scan[i] = (value + left) & 255
            elif filter_type == 2: scan[i] = (value + above) & 255
            elif filter_type == 3: scan[i] = (value + ((left + above) // 2)) & 255
            elif filter_type == 4: scan[i] = (value + _paeth(left, above, upper_left)) & 255
            elif filter_type != 0: raise ValueError(f"Unsupported PNG filter {filter_type}")
        output.extend(scan); previous = scan
    return width, height, bytes(output)


def _world_pixel(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    scale = 256 * 2**zoom
    lat = max(-85.0511, min(85.0511, lat))
    return ((lon + 180) / 360 * scale,
            (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * scale)


def _tile(z: int, x: int, y: int) -> tuple[int, int, bytes]:
    cache = Path.home() / ".cache" / "dem-optimizer-art" / "tiles" / str(z) / str(x)
    path = cache / f"{y}.png"
    if path.exists():
        data = path.read_bytes()
    else:
        request = urllib.request.Request(TERRAIN_URL.format(z=z, x=x, y=y), headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return decode_rgb_png(data)


def _zoom_for_bbox(north: float, south: float, east: float, west: float) -> int:
    span = max(east - west, north - south, 0.002)
    zoom = max(7, min(12, round(math.log2(720 / span))))
    while zoom > 7:
        left, top = _world_pixel(north, west, zoom)
        right, bottom = _world_pixel(south, east, zoom)
        count = (int(right // 256) - int(left // 256) + 1) * (int(bottom // 256) - int(top // 256) + 1)
        if count <= 36: break
        zoom -= 1
    return zoom


def fetch_surface(north: float, south: float, east: float, west: float,
                  resolution: int = 96, smoothing: int = 8) -> tuple[Surface, dict]:
    if not (-85 <= south < north <= 85 and -180 <= west < east <= 180):
        raise ValueError("Invalid bounds; the selection must not cross the date line")
    if max(north - south, east - west) > 8:
        raise ValueError("Selection is too large; choose an area under 8° across")
    zoom = _zoom_for_bbox(north, south, east, west)
    left, top = _world_pixel(north, west, zoom)
    right, bottom = _world_pixel(south, east, zoom)
    tiles = {}
    for tx in range(int(left // 256), int(right // 256) + 1):
        for ty in range(int(top // 256), int(bottom // 256) + 1):
            tiles[tx, ty] = _tile(zoom, tx, ty)

    def elevation(px: float, py: float) -> float:
        tx, ty = int(px // 256), int(py // 256)
        width, height, rgb = tiles[tx, ty]
        ix, iy = min(width - 1, int(px - tx * 256)), min(height - 1, int(py - ty * 256))
        offset = (iy * width + ix) * 3
        red, green, blue = rgb[offset:offset + 3]
        return red * 256 + green + blue / 256 - 32768

    grid = [[elevation(left + (right - left) * x / (resolution - 1),
                       top + (bottom - top) * y / (resolution - 1))
             for x in range(resolution)] for y in range(resolution)]
    raw_min, raw_max = min(map(min, grid)), max(map(max, grid))
    surface = Surface(normalize(smooth(grid, smoothing)))
    mean_latitude = (north + south) / 2
    width_km = (east - west) * 111.32 * math.cos(math.radians(mean_latitude))
    height_km = (north - south) * 111.32
    relief_km = max(0.001, (raw_max - raw_min) / 1000)
    # Match projected vertical relief to real relief/horizontal extent. The
    # 1322/540 factor maps physical proportions into this projection's pixels.
    natural_scale = max(0.08, min(1.2, relief_km / max(width_km, height_km, 0.001) * (1322 / 540)))
    return surface, {"zoom": zoom, "elevation_min": round(raw_min), "elevation_max": round(raw_max),
                     "width_km": round(width_km, 1), "height_km": round(height_km, 1),
                     "natural_vertical_scale": round(natural_scale, 3),
                     "tiles": len(tiles), "source": "AWS Terrain Tiles"}


def search_places(query: str) -> list[dict]:
    global _last_search
    key = query.strip().lower()
    if len(key) < 2:
        raise ValueError("Enter at least two characters")
    if key in _search_cache:
        return _search_cache[key]
    with _search_lock:
        delay = 1.05 - (time.monotonic() - _last_search)
        if delay > 0: time.sleep(delay)
        params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "limit": 5, "addressdetails": 0})
        request = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + params,
                                         headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=15) as response:
            results = json.loads(response.read())
        _last_search = time.monotonic()
    cleaned = [{"name": item["display_name"], "lat": float(item["lat"]), "lon": float(item["lon"]),
                "bounds": [float(value) for value in item["boundingbox"]]} for item in results]
    _search_cache[key] = cleaned
    return cleaned
