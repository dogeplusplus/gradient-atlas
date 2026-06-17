from __future__ import annotations

import math
from pathlib import Path

from .dem import Surface
from .optimizers import EQUATIONS, OPTIMIZER_COLORS, run


PALETTES = {
    "spectrum": ("#3326a8", "#126de0", "#00c5cf", "#56dc75", "#f5e94b", "#ff8a2b", "#e9364f"),
    "ocean": ("#152a5b", "#175d8d", "#2ca6a4", "#a7d46f", "#f2d15c"),
    "magma": ("#251255", "#7b1f70", "#d33f5f", "#f98e52", "#f9e784"),
    "mono": ("#13283b", "#36566e", "#7691a3", "#c3ced4"),
}

W, H = 1200, 1600
INK, PAPER = "#17324d", "#f8f5ee"


def _mix(a: str, b: str, t: float) -> str:
    av, bv = ([int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(av, bv))


def _colour(z: float, palette: tuple[str, ...]) -> str:
    scaled = max(0.0, min(0.9999, (z + 1.8) / 3.6)) * (len(palette) - 1)
    i = int(scaled)
    return _mix(palette[i], palette[i + 1], scaled - i)


def _project(x: float, y: float, z: float, vertical_scale: float) -> tuple[float, float]:
    return 600 + 110.2 * (x - y), 740 + 45 * (x + y) - 150 * vertical_scale * z


def _points(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def render(surface: Surface, config: dict, output: str | Path) -> Path:
    title = config.get("title", "UNTITLED DEM").upper()
    steps = int(config.get("steps", 22))
    grid_lines = int(config.get("grid_lines", 75))
    vertical_scale = float(config.get("vertical_scale", 1.0))
    fill_opacity = float(config.get("fill_opacity", 0.10))
    palette_value = config.get("palette", "spectrum")
    palette = tuple(palette_value) if isinstance(palette_value, list) else PALETTES.get(palette_value, PALETTES["spectrum"])
    methods = config.get("optimizers", list(OPTIMIZER_COLORS))
    starts_uv = config.get("start_points", [[0.62, 0.42]])
    starts = [(-3 + 6 * float(u), -3 + 6 * float(v)) for u, v in starts_uv]

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
           '<g fill="none" stroke-linecap="round" stroke-linejoin="round">']

    resolution = 68
    cells = []
    for ix in range(resolution):
        for iy in range(resolution):
            x0, x1 = -3 + 6 * ix / resolution, -3 + 6 * (ix + 1) / resolution
            y0, y1 = -3 + 6 * iy / resolution, -3 + 6 * (iy + 1) / resolution
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            zs = [surface.value(x, y) for x, y in corners]
            cells.append((x0 + y0, [_project(x, y, z, vertical_scale) for (x, y), z in zip(corners, zs)], sum(zs) / 4))
    for _, points, z in sorted(cells):
        c = _colour(z, palette)
        svg.append(f'<polygon points="{_points(points)}" fill="{c}" fill-opacity="{fill_opacity}" stroke="none"/>')

    samples = 160
    for family in ("x", "y"):
        for i in range(grid_lines):
            fixed = -3 + 6 * i / (grid_lines - 1)
            points, zs = [], []
            for j in range(samples):
                moving = -3 + 6 * j / (samples - 1)
                x, y = (moving, fixed) if family == "x" else (fixed, moving)
                z = surface.value(x, y)
                points.append(_project(x, y, z, vertical_scale)); zs.append(z)
            major = i % 6 == 0
            for j, (a, b) in enumerate(zip(points, points[1:])):
                c = _colour((zs[j] + zs[j + 1]) / 2, palette)
                svg.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{c}" stroke-width="{0.95 if major else 0.40}" opacity="{0.72 if major else 0.38}"/>')

    for start_index, start in enumerate(starts):
        for method in methods:
            colour = OPTIMIZER_COLORS[method]
            path = run(surface, method, start, steps)
            projected = [_project(x, y, surface.value(x, y) + 0.055, vertical_scale) for x, y in path]
            svg.append(f'<polyline points="{_points(projected)}" stroke="{PAPER}" stroke-width="7" opacity="0.7"/>')
            svg.append(f'<polyline points="{_points(projected)}" stroke="{colour}" stroke-width="{3.2 if start_index == 0 else 2.2}" opacity="{0.95 if start_index == 0 else 0.62}"/>')
            end = projected[-1]
            svg.append(f'<circle cx="{end[0]:.1f}" cy="{end[1]:.1f}" r="4.8" fill="{colour}" stroke="{PAPER}" stroke-width="2"/>')
        p = _project(start[0], start[1], surface.value(*start) + 0.06, vertical_scale)
        svg.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="8" fill="{PAPER}" stroke="{INK}" stroke-width="2.5"/>')
        svg.append(f'<text x="{p[0] + 12:.1f}" y="{p[1] - 10:.1f}" fill="{INK}" font-family="monospace" font-size="12">START {start_index + 1}</text>')
    svg.append('</g>')

    # Chromatic plotter-registration title, using the DEM name—not a generic heading.
    for i, method in enumerate(methods):
        offset = (i - (len(methods) - 1) / 2) * 1.4
        svg.append(f'<text x="{72 + offset:.1f}" y="1260" fill="none" stroke="{OPTIMIZER_COLORS[method]}" stroke-width="1.2" opacity="0.7" font-family="Helvetica,Arial,sans-serif" font-size="44" letter-spacing="5">{title}</text>')
    svg.append(f'<text x="72" y="1260" fill="{INK}" font-family="Helvetica,Arial,sans-serif" font-size="44" letter-spacing="5">{title}</text>')
    svg.append(f'<text x="75" y="1300" fill="{INK}" opacity="0.60" font-family="Helvetica,Arial,sans-serif" font-size="13" letter-spacing="2">OPTIMIZER TRAJECTORIES · {steps} STEPS · {len(starts)} START POINT(S)</text>')
    svg.append(f'<line x1="75" y1="1325" x2="1125" y2="1325" stroke="{INK}" opacity="0.35"/>')
    positions = [(75, 1360), (75, 1410), (75, 1460), (625, 1360), (625, 1410), (625, 1460)]
    for method, (x, y) in zip(methods, positions):
        c = OPTIMIZER_COLORS[method]
        svg.append(f'<line x1="{x}" y1="{y - 5}" x2="{x + 25}" y2="{y - 5}" stroke="{c}" stroke-width="4"/>')
        svg.append(f'<text x="{x + 35}" y="{y}" fill="{c}" font-family="monospace" font-size="12">{method.upper()}</text>')
        svg.append(f'<text x="{x + 115}" y="{y}" fill="{INK}" font-family="monospace" font-size="10.5">{EQUATIONS[method]}</text>')
    svg.extend([f'<line x1="75" y1="1495" x2="1125" y2="1495" stroke="{INK}" opacity="0.35"/>',
                f'<text x="75" y="1530" fill="{INK}" opacity="0.55" font-family="monospace" font-size="11">gₜ = ∇L(θₜ) · coordinates normalized to the supplied DEM</text>', '</svg>'])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(svg), encoding="utf-8")
    return output
