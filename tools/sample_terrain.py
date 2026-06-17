#!/usr/bin/env python3
"""Sample a real-world elevation tile into a smooth CSV loss surface (macOS)."""

from __future__ import annotations

import argparse
import csv
import math
import struct
import subprocess
import tempfile
from pathlib import Path


def world_pixel(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    scale = 256 * 2**zoom
    x = (lon + 180) / 360 * scale
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * scale
    return x, y


def read_bmp(path: Path) -> list[list[float]]:
    data = path.read_bytes()
    offset = struct.unpack_from("<I", data, 10)[0]
    width, signed_height = struct.unpack_from("<ii", data, 18)
    top_down, height = signed_height < 0, abs(signed_height)
    stride = ((width * 3 + 3) // 4) * 4
    rows = []
    for y in range(height):
        source_y = y if top_down else height - 1 - y
        start = offset + source_y * stride
        row = []
        for x in range(width):
            blue, green, red = data[start + x * 3:start + x * 3 + 3]
            row.append(red * 256 + green + blue / 256 - 32768)
        rows.append(row)
    return rows


def blur(grid: list[list[float]], passes: int) -> list[list[float]]:
    for _ in range(passes):
        height, width = len(grid), len(grid[0])
        grid = [[
            sum(grid[yy][xx] for yy in range(max(0, y - 1), min(height, y + 2))
                for xx in range(max(0, x - 1), min(width, x + 2)))
            / ((min(height, y + 2) - max(0, y - 1)) * (min(width, x + 2) - max(0, x - 1)))
            for x in range(width)] for y in range(height)]
    return grid


def sample(name: str, lat: float, lon: float, lat_span: float, lon_span: float,
           output: Path, zoom: int = 10, size: int = 96, blur_passes: int = 5) -> None:
    left, top = world_pixel(lat + lat_span / 2, lon - lon_span / 2, zoom)
    right, bottom = world_pixel(lat - lat_span / 2, lon + lon_span / 2, zoom)
    min_tx, max_tx = int(left // 256), int(right // 256)
    min_ty, max_ty = int(top // 256), int(bottom // 256)
    tiles: dict[tuple[int, int], list[list[float]]] = {}
    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        for tx in range(min_tx, max_tx + 1):
            for ty in range(min_ty, max_ty + 1):
                png, bmp = temp_path / f"{tx}-{ty}.png", temp_path / f"{tx}-{ty}.bmp"
                url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{zoom}/{tx}/{ty}.png"
                subprocess.run(["curl", "-L", "--fail", "--silent", "--show-error", url, "-o", str(png)], check=True)
                subprocess.run(["sips", "-s", "format", "bmp", str(png), "--out", str(bmp)], check=True,
                               stdout=subprocess.DEVNULL)
                tiles[tx, ty] = read_bmp(bmp)

    def elevation(px: float, py: float) -> float:
        tx, ty = int(px // 256), int(py // 256)
        ix, iy = int(px % 256), int(py % 256)
        return tiles[tx, ty][iy][ix]

    grid = [[elevation(left + (right - left) * x / (size - 1), top + (bottom - top) * y / (size - 1))
             for x in range(size)] for y in range(size)]
    grid = blur(grid, blur_passes)
    low, high = min(map(min, grid)), max(map(max, grid))
    normalized = [[(value - low) / (high - low) * 3.6 - 1.8 for value in row] for row in grid]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([f"# {name}; {lat:.4f},{lon:.4f}; raw range {low:.0f}–{high:.0f} m; blur {blur_passes}"])
        writer.writerows([[f"{value:.5f}" for value in row] for row in normalized])
    print(f"Wrote {output}: {low:.0f}–{high:.0f} m")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("lat", type=float)
    parser.add_argument("lon", type=float)
    parser.add_argument("lat_span", type=float)
    parser.add_argument("lon_span", type=float)
    parser.add_argument("output", type=Path)
    parser.add_argument("--zoom", type=int, default=10)
    parser.add_argument("--blur", type=int, default=5)
    args = parser.parse_args()
    sample(args.name, args.lat, args.lon, args.lat_span, args.lon_span, args.output, args.zoom, blur_passes=args.blur)


if __name__ == "__main__":
    main()
