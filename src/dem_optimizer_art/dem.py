from __future__ import annotations

import csv
import math
from pathlib import Path


Grid = list[list[float]]


def _load_csv(path: Path) -> Grid:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if rows and rows[0] and rows[0][0].startswith("#"):
        rows = rows[1:]
    return [[float(value) for value in row] for row in rows if row]


def _load_image(path: Path) -> Grid:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("PNG/JPEG input needs: pip install 'gradient-atlas[images]'") from exc
    image = Image.open(path)
    if image.mode in ("I", "F", "I;16"):
        return [[float(image.getpixel((x, y))) for x in range(image.width)] for y in range(image.height)]
    grey = image.convert("L")
    return [[float(grey.getpixel((x, y))) for x in range(grey.width)] for y in range(grey.height)]


def _load_geotiff(path: Path) -> Grid:
    try:
        import rasterio
    except ImportError as exc:
        raise RuntimeError("GeoTIFF input needs: pip install 'gradient-atlas[geotiff]'") from exc
    with rasterio.open(path) as source:
        band = source.read(1, masked=True)
        fill = float(band.mean())
        return band.filled(fill).astype(float).tolist()


def load_dem(path: str | Path) -> Grid:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt"):
        return _load_csv(path)
    if suffix in (".tif", ".tiff"):
        return _load_geotiff(path)
    if suffix in (".png", ".jpg", ".jpeg"):
        return _load_image(path)
    raise ValueError(f"Unsupported DEM format: {suffix}. Use CSV, GeoTIFF, PNG, or JPEG.")


def resample(grid: Grid, size: int = 96) -> Grid:
    height, width = len(grid), len(grid[0])
    output = []
    for j in range(size):
        v = j / (size - 1) * (height - 1)
        y, fy = int(v), v - int(v)
        y1 = min(y + 1, height - 1)
        row = []
        for i in range(size):
            u = i / (size - 1) * (width - 1)
            x, fx = int(u), u - int(u)
            x1 = min(x + 1, width - 1)
            row.append(grid[y][x] * (1 - fx) * (1 - fy) + grid[y][x1] * fx * (1 - fy)
                       + grid[y1][x] * (1 - fx) * fy + grid[y1][x1] * fx * fy)
        output.append(row)
    return output


def smooth(grid: Grid, passes: int) -> Grid:
    for _ in range(passes):
        height, width = len(grid), len(grid[0])
        grid = [[sum(grid[yy][xx] for yy in range(max(0, y - 1), min(height, y + 2))
                     for xx in range(max(0, x - 1), min(width, x + 2)))
                 / ((min(height, y + 2) - max(0, y - 1)) * (min(width, x + 2) - max(0, x - 1)))
                 for x in range(width)] for y in range(height)]
    return grid


def normalize(grid: Grid, low: float = -1.8, high: float = 1.8) -> Grid:
    minimum, maximum = min(map(min, grid)), max(map(max, grid))
    span = maximum - minimum or 1.0
    return [[low + (value - minimum) / span * (high - low) for value in row] for row in grid]


class Surface:
    def __init__(self, grid: Grid):
        self.grid = grid
        self.height, self.width = len(grid), len(grid[0])

    def value(self, x: float, y: float) -> float:
        u = max(0.0, min(self.width - 1.0001, (x + 3) / 6 * (self.width - 1)))
        v = max(0.0, min(self.height - 1.0001, (y + 3) / 6 * (self.height - 1)))
        i, j, fu, fv = int(u), int(v), u - int(u), v - int(v)
        return (self.grid[j][i] * (1 - fu) * (1 - fv)
                + self.grid[j][i + 1] * fu * (1 - fv)
                + self.grid[j + 1][i] * (1 - fu) * fv
                + self.grid[j + 1][i + 1] * fu * fv)

    def gradient(self, x: float, y: float, h: float = 0.025) -> tuple[float, float]:
        return ((self.value(x + h, y) - self.value(x - h, y)) / (2 * h),
                (self.value(x, y + h) - self.value(x, y - h)) / (2 * h))


def prepare_surface(path: str | Path, smoothing: int = 8, size: int = 96) -> Surface:
    return Surface(normalize(smooth(resample(load_dem(path), size), smoothing)))
