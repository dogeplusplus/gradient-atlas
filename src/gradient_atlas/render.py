from __future__ import annotations

import math
from html import escape
from pathlib import Path

from .dem import Surface
from .optimizers import equation_lines, OPTIMIZER_COLORS, run


PALETTES = {
    "spectrum": ("#3326a8", "#126de0", "#00c5cf", "#56dc75", "#f5e94b", "#ff8a2b", "#e9364f"),
    "ocean": ("#152a5b", "#175d8d", "#2ca6a4", "#a7d46f", "#f2d15c"),
    "magma": ("#251255", "#7b1f70", "#d33f5f", "#f98e52", "#f9e784"),
    "mono": ("#13283b", "#36566e", "#7691a3", "#c3ced4"),
    "aurora": ("#102039", "#244c95", "#18a7c9", "#65f3b5", "#f7ff9b"),
    "ember": ("#1c1028", "#5f1f62", "#c22f5d", "#ff7a3d", "#ffe08a"),
    "twilight": ("#111827", "#263a8b", "#6b49c8", "#d45fa3", "#ffd6a5"),
    "topo": ("#092a36", "#0f6f73", "#7bc96f", "#f4d35e", "#f76f53"),
    "glacier": ("#081923", "#123c69", "#2c7da0", "#8edce6", "#f0fbff"),
}

W, H = 1200, 1600
THEMES = {
    "light": {
        "paper": "#f8f5ee",
        "ink": "#17324d",
        "muted": "#17324d",
        "rule_opacity": 0.35,
        "grid_opacity": (0.72, 0.38),
        "min_fill_opacity": 0.0,
    },
    "dark": {
        "paper": "#071019",
        "ink": "#edf8ff",
        "muted": "#b7cbd8",
        "rule_opacity": 0.42,
        "grid_opacity": (0.96, 0.66),
        "min_fill_opacity": 0.22,
    },
}
INK, PAPER = THEMES["light"]["ink"], THEMES["light"]["paper"]


def _mix(a: str, b: str, t: float) -> str:
    av, bv = ([int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(av, bv))


def _colour(z: float, palette: tuple[str, ...]) -> str:
    scaled = max(0.0, min(0.9999, (z + 1.8) / 3.6)) * (len(palette) - 1)
    i = int(scaled)
    return _mix(palette[i], palette[i + 1], scaled - i)


def _project(x: float, y: float, z: float, vertical_scale: float,
             page_width: int = W) -> tuple[float, float]:
    horizontal_scale = page_width / W
    return page_width / 2 + 110.2 * horizontal_scale * (x - y), 740 + 45 * (x + y) - 150 * vertical_scale * z


def _projector(surface: Surface, vertical_scale: float, auto_fit: bool,
               top: float, bottom: float, page_width: int = W):
    """Fit the complete surface to the art bounds without distorting its aspect."""
    if not auto_fit:
        return lambda x, y, z: _project(x, y, z, vertical_scale, page_width)
    projected = []
    for j in range(49):
        y = -3 + 6 * j / 48
        for i in range(49):
            x = -3 + 6 * i / 48
            projected.append(_project(x, y, surface.value(x, y), vertical_scale, page_width))
    x_low, x_high = min(x for x, _ in projected), max(x for x, _ in projected)
    y_low, y_high = min(y for _, y in projected), max(y for _, y in projected)
    side = max(42.0, page_width * 0.035)
    scale = min((page_width - 2 * side) / (x_high - x_low or 1),
                (bottom - top) / (y_high - y_low or 1))
    fitted_width = (x_high - x_low) * scale
    fitted_height = (y_high - y_low) * scale
    left = (page_width - fitted_width) / 2
    fitted_top = top + ((bottom - top) - fitted_height) / 2

    def fitted(x: float, y: float, z: float) -> tuple[float, float]:
        px, py = _project(x, y, z, vertical_scale, page_width)
        return left + (px - x_low) * scale, fitted_top + (py - y_low) * scale

    return fitted


def _points(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _clean_trajectory(points: list[tuple[float, float]], min_distance: float = 0.8) -> list[tuple[float, float]]:
    """Remove visually stationary samples while retaining the true start and end."""
    if len(points) < 3:
        return points
    cleaned = [points[0]]
    for point in points[1:-1]:
        if math.dist(point, cleaned[-1]) >= min_distance:
            cleaned.append(point)
    if math.dist(points[-1], cleaned[-1]) >= 0.1:
        cleaned.append(points[-1])
    return cleaned


def _trajectory_d(points: list[tuple[float, float]], smooth: bool = True) -> str:
    """Create a restrained Catmull–Rom spline through optimizer samples."""
    if not points:
        return ""
    if len(points) < 3 or not smooth:
        return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
    parts = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    tension = 0.62
    for i in range(len(points) - 1):
        p0 = points[max(0, i - 1)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(len(points) - 1, i + 2)]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 6,
              p1[1] + (p2[1] - p0[1]) * tension / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 6,
              p2[1] - (p3[1] - p1[1]) * tension / 6)
        parts.append(
            f"C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
        )
    return " ".join(parts)


def _direction_chevron(points: list[tuple[float, float]]) -> str:
    """Return a small plotter-friendly arrow placed late in the trajectory."""
    if len(points) < 3:
        return ""
    index = max(1, min(len(points) - 2, round((len(points) - 1) * 0.72)))
    before, tip, after = points[index - 1], points[index], points[index + 1]
    dx, dy = after[0] - before[0], after[1] - before[1]
    length = math.hypot(dx, dy)
    if length < 0.1:
        return ""
    ux, uy = dx / length, dy / length
    bx, by = tip[0] - ux * 8.0, tip[1] - uy * 8.0
    px, py = -uy * 4.0, ux * 4.0
    return f"M {bx + px:.1f} {by + py:.1f} L {tip[0]:.1f} {tip[1]:.1f} L {bx - px:.1f} {by - py:.1f}"


def _start_label(index: int) -> str:
    labels = ("α", "β", "γ", "δ", "ε", "ζ", "η", "κ", "λ")
    if index < len(labels):
        return f"θ₀·{labels[index]}"
    return f"θ₀·{index + 1}"


def _jitter(ix: int, iy: int) -> tuple[float, float]:
    seed = (ix * 73856093) ^ (iy * 19349663)
    a = ((seed & 1023) / 1023) - 0.5
    b = (((seed >> 10) & 1023) / 1023) - 0.5
    return a, b


def _polygon_vertices(size: int) -> list[list[tuple[float, float]]]:
    step = 6 / (size - 1)
    vertices = []
    for y in range(size):
        row = []
        for x in range(size):
            px, py = -3 + step * x, -3 + step * y
            if 0 < x < size - 1 and 0 < y < size - 1:
                jx, jy = _jitter(x, y)
                px += jx * step * 0.42
                py += jy * step * 0.42
            row.append((px, py))
        vertices.append(row)
    return vertices


def _contour_segments(surface: Surface, levels: int = 14, size: int = 72):
    """Return projected-ready contour segments using marching squares."""
    samples = [[surface.value(-3 + 6 * x / size, -3 + 6 * y / size)
                for x in range(size + 1)] for y in range(size + 1)]
    low, high = min(map(min, samples)), max(map(max, samples))
    contours = []
    for level_index in range(1, levels + 1):
        level = low + (high - low) * level_index / (levels + 1)
        segments = []
        for y in range(size):
            for x in range(size):
                corners = [
                    (-3 + 6 * x / size, -3 + 6 * y / size, samples[y][x]),
                    (-3 + 6 * (x + 1) / size, -3 + 6 * y / size, samples[y][x + 1]),
                    (-3 + 6 * (x + 1) / size, -3 + 6 * (y + 1) / size, samples[y + 1][x + 1]),
                    (-3 + 6 * x / size, -3 + 6 * (y + 1) / size, samples[y + 1][x]),
                ]
                hits = []
                for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
                    za, zb = corners[a][2], corners[b][2]
                    if (za < level <= zb) or (zb < level <= za):
                        t = (level - za) / (zb - za)
                        hits.append((corners[a][0] + (corners[b][0] - corners[a][0]) * t,
                                     corners[a][1] + (corners[b][1] - corners[a][1]) * t))
                if len(hits) == 2:
                    segments.append((hits[0], hits[1]))
                elif len(hits) == 4:
                    segments.extend(((hits[0], hits[1]), (hits[2], hits[3])))
        contours.append((level, segments))
    return contours


def _trajectory_marker(x: float, y: float, index: int, colour: str, paper: str,
                       radius: float, opacity: float) -> str:
    """Give every optimizer a recognizable glyph as well as a colour."""
    shape = index % 6
    common = f'stroke="{colour}" stroke-width="1.5" opacity="{opacity}"'
    if shape == 0:
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{paper}" {common}/>'
    if shape == 1:
        return f'<rect x="{x-radius:.1f}" y="{y-radius:.1f}" width="{2*radius:.1f}" height="{2*radius:.1f}" rx="0.8" fill="{paper}" {common}/>'
    if shape == 2:
        return f'<polygon points="{x:.1f},{y-radius-0.8:.1f} {x+radius+0.8:.1f},{y:.1f} {x:.1f},{y+radius+0.8:.1f} {x-radius-0.8:.1f},{y:.1f}" fill="{paper}" {common}/>'
    if shape == 3:
        return f'<polygon points="{x:.1f},{y-radius-1:.1f} {x+radius+1:.1f},{y+radius:.1f} {x-radius-1:.1f},{y+radius:.1f}" fill="{paper}" {common}/>'
    if shape == 4:
        return f'<path d="M {x-radius:.1f} {y:.1f} L {x+radius:.1f} {y:.1f} M {x:.1f} {y-radius:.1f} L {x:.1f} {y+radius:.1f}" {common} fill="none"/>'
    return f'<path d="M {x-radius:.1f} {y-radius:.1f} L {x+radius:.1f} {y+radius:.1f} M {x+radius:.1f} {y-radius:.1f} L {x-radius:.1f} {y+radius:.1f}" {common} fill="none"/>'


def render(surface: Surface, config: dict, output: str | Path) -> Path:
    print_width = float(config.get("print_width", 12.0))
    print_height = float(config.get("print_height", 16.0))
    if not (4 <= print_width <= 60 and 4 <= print_height <= 60):
        raise ValueError("Print width and height must be between 4 and 60 inches")
    if not 0.5 <= print_width / print_height <= 2.0:
        raise ValueError("Print aspect ratio must be between 1:2 and 2:1")
    if print_height >= print_width:
        page_width, page_height = W, round(W * print_height / print_width)
    else:
        page_height, page_width = 1200, round(1200 * print_width / print_height)
    title = escape(str(config.get("title", "UNTITLED DEM")).upper())
    steps = int(config.get("steps", 22))
    step_length = float(config.get("step_length", 1.0))
    grid_lines = int(config.get("grid_lines", 75))
    mesh_style = str(config.get("mesh_style", "grid")).lower()
    vertical_scale = float(config.get("vertical_scale", 1.0))
    fill_opacity = float(config.get("fill_opacity", 0.10))
    theme_name = str(config.get("theme", "light")).lower()
    theme = THEMES.get(theme_name, THEMES["light"])
    paper, ink, muted = theme["paper"], theme["ink"], theme["muted"]
    major_grid_opacity, minor_grid_opacity = theme["grid_opacity"]
    fill_opacity = max(fill_opacity, float(theme["min_fill_opacity"]))
    if mesh_style == "triangles":
        fill_opacity = max(fill_opacity, 0.42 if theme_name == "dark" else 0.30)
        major_grid_opacity, minor_grid_opacity = min(major_grid_opacity, 0.58), min(minor_grid_opacity, 0.34)
    palette_value = config.get("palette", "spectrum")
    palette = tuple(palette_value) if isinstance(palette_value, list) else PALETTES.get(palette_value, PALETTES["spectrum"])
    methods = config.get("optimizers", list(OPTIMIZER_COLORS))
    objective = config.get("objective", "descent")
    trajectory_style = config.get("trajectory_style", "flowing")
    equations = equation_lines(objective)
    starts_uv = config.get("start_points", [[0.62, 0.42]])
    starts = [(-3 + 6 * float(u), -3 + 6 * float(v)) for u, v in starts_uv]
    has_print_size = "print_width" in config or "print_height" in config
    surface_bottom = page_height - 415 if has_print_size else float(config.get("surface_bottom", 1185))
    project = _projector(surface, vertical_scale, bool(config.get("auto_fit", True)),
                         float(config.get("surface_top", 90)), surface_bottom, page_width)

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {page_width} {page_height}" width="{print_width:g}in" height="{print_height:g}in">',
           f'<rect width="{page_width}" height="{page_height}" fill="{paper}"/>',
           '<g fill="none" stroke-linecap="round" stroke-linejoin="round">']

    resolution = max(18, min(38, round(grid_lines * 0.42))) if mesh_style == "triangles" else 68
    cells = []
    if mesh_style == "triangles":
        vertices = _polygon_vertices(resolution + 1)
        for ix in range(resolution):
            for iy in range(resolution):
                v00, v10 = vertices[iy][ix], vertices[iy][ix + 1]
                v01, v11 = vertices[iy + 1][ix], vertices[iy + 1][ix + 1]
                polygons = [[v00, v10, v01], [v10, v11, v01]] if (ix + iy) % 2 else [[v00, v10, v11], [v00, v11, v01]]
                for corners in polygons:
                    zs = [surface.value(x, y) for x, y in corners]
                    cells.append((sum(x + y for x, y in corners) / len(corners),
                                  [project(x, y, z) for (x, y), z in zip(corners, zs)], sum(zs) / len(zs)))
    else:
        for ix in range(resolution):
            for iy in range(resolution):
                x0, x1 = -3 + 6 * ix / resolution, -3 + 6 * (ix + 1) / resolution
                y0, y1 = -3 + 6 * iy / resolution, -3 + 6 * (iy + 1) / resolution
                corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                zs = [surface.value(x, y) for x, y in corners]
                cells.append((x0 + y0, [project(x, y, z) for (x, y), z in zip(corners, zs)], sum(zs) / len(zs)))
    for _, points, z in sorted(cells):
        c = _colour(z, palette)
        svg.append(f'<polygon points="{_points(points)}" fill="{c}" fill-opacity="{fill_opacity}" stroke="none"/>')

    if mesh_style == "triangles":
        mesh = resolution + 1
        projected = [[project(x, y, surface.value(x, y)) for x, y in row] for row in vertices]
        for y in range(mesh - 1):
            for x in range(mesh - 1):
                edges = ((projected[y][x], projected[y][x + 1], vertices[y][x], vertices[y][x + 1]),
                         (projected[y][x], projected[y + 1][x], vertices[y][x], vertices[y + 1][x]))
                if (x + y) % 2:
                    edges += ((projected[y][x + 1], projected[y + 1][x], vertices[y][x + 1], vertices[y + 1][x]),)
                else:
                    edges += ((projected[y][x], projected[y + 1][x + 1], vertices[y][x], vertices[y + 1][x + 1]),)
                major = x % 6 == 0 or y % 6 == 0
                for a, b, va, vb in edges:
                    c = _colour((surface.value(*va) + surface.value(*vb)) / 2, palette)
                    svg.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{c}" stroke-width="{0.65 if major else 0.28}" opacity="{major_grid_opacity if major else minor_grid_opacity}"/>')
    elif mesh_style == "contours":
        for level_index, (level, segments) in enumerate(_contour_segments(surface)):
            colour = _colour(level, palette)
            major = level_index % 4 == 3
            for (x1, y1), (x2, y2) in segments:
                a, b = project(x1, y1, level + 0.01), project(x2, y2, level + 0.01)
                svg.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{colour}" stroke-width="{1.7 if major else 0.75}" opacity="{0.92 if major else 0.58}"/>')
    else:
        samples = 160
        for family in ("x", "y"):
            for i in range(grid_lines):
                fixed = -3 + 6 * i / (grid_lines - 1)
                points, zs = [], []
                for j in range(samples):
                    moving = -3 + 6 * j / (samples - 1)
                    x, y = (moving, fixed) if family == "x" else (fixed, moving)
                    z = surface.value(x, y)
                    points.append(project(x, y, z)); zs.append(z)
                major = i % 6 == 0
                for j, (a, b) in enumerate(zip(points, points[1:])):
                    c = _colour((zs[j] + zs[j + 1]) / 2, palette)
                    svg.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{c}" stroke-width="{0.95 if major else 0.40}" opacity="{major_grid_opacity if major else minor_grid_opacity}"/>')

    trajectory_art = []
    for start_index, start in enumerate(starts):
        for method_index, method in enumerate(methods):
            colour = OPTIMIZER_COLORS[method]
            path = run(surface, method, start, steps, objective, step_length)
            projected = _clean_trajectory([
                project(x, y, surface.value(x, y) + 0.055) for x, y in path
            ])
            smooth = trajectory_style != "technical"
            path_d = _trajectory_d(projected, smooth=smooth)
            primary = start_index == 0
            trajectory_art.append({
                "colour": colour, "path_d": path_d, "points": projected, "primary": primary,
                "method": method, "method_index": method_index,
                "length": sum(math.dist(a, b) for a, b in zip(projected, projected[1:])),
            })

    # Draw shared halos before any coloured ink; otherwise later paths erase earlier ones.
    trajectory_art.sort(key=lambda item: item["length"], reverse=True)
    for item in trajectory_art:
        svg.append(f'<path d="{item["path_d"]}" stroke="{paper}" stroke-width="{8.2 if item["primary"] else 6.2}" opacity="0.82"/>')
    if trajectory_style == "flowing":
        for item in trajectory_art:
            svg.append(f'<path d="{item["path_d"]}" stroke="{item["colour"]}" stroke-width="{5.4 if item["primary"] else 4.0}" opacity="{0.22 if item["primary"] else 0.15}"/>')
    dash_patterns = ("", "12 5", "2 4", "15 4 2 4", "7 3", "1 3")
    for item in trajectory_art:
        encoded = trajectory_style == "encoded"
        dash = f' stroke-dasharray="{dash_patterns[item["method_index"] % 6]}"' if encoded and item["method_index"] else ""
        width = 3.2 if encoded and item["primary"] else (2.8 if item["primary"] else 2.0)
        svg.append(f'<path d="{item["path_d"]}" stroke="{item["colour"]}" stroke-width="{width}" opacity="{0.98 if item["primary"] else 0.72}"{dash}/>')

    for item in trajectory_art:
        projected = item["points"]
        colour = item["colour"]
        primary = item["primary"]
        if trajectory_style in {"flowing", "technical", "constellation", "encoded"} and len(projected) > 3:
            marker_count = 6 if trajectory_style == "constellation" else (4 if trajectory_style in {"flowing", "encoded"} else min(8, len(projected) - 2))
            marker_indices = sorted({round(i * (len(projected) - 1) / (marker_count + 1)) for i in range(1, marker_count + 1)})
            for marker_index in marker_indices:
                mx, my = projected[marker_index]
                svg.append(_trajectory_marker(mx, my, item["method_index"], colour, paper,
                                              3.0 if trajectory_style == "constellation" else (2.5 if primary else 2),
                                              0.95 if primary else 0.72))
            chevron = _direction_chevron(projected)
            if chevron:
                svg.append(f'<path d="{chevron}" stroke="{colour}" stroke-width="{2.2 if primary else 1.7}" opacity="{0.95 if primary else 0.68}"/>')
        end = projected[-1]
        svg.append(f'<circle cx="{end[0]:.1f}" cy="{end[1]:.1f}" r="4.8" fill="{colour}" stroke="{paper}" stroke-width="2"/>')

    for start_index, start in enumerate(starts):
        p = project(start[0], start[1], surface.value(*start) + 0.06)
        svg.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="8" fill="{paper}" stroke="{ink}" stroke-width="2.5"/>')
        svg.append(f'<text x="{p[0] + 12:.1f}" y="{p[1] - 10:.1f}" fill="{ink}" opacity="0.9" font-family="monospace" font-size="13">{_start_label(start_index)}</text>')
    svg.append('</g>')

    # Museum-label typography: title first, then a compact scientific key.
    title_y = page_height - 352
    title_size = min(60, max(42, (page_width - 220) / max(1, len(title) * 0.62)))
    svg.append(f'<text x="72" y="{title_y}" fill="{ink}" font-family="Helvetica,Arial,sans-serif" font-weight="700" font-size="{title_size:.1f}" letter-spacing="2.5">{title}</text>')
    segment_width = 66
    for i, method in enumerate(methods):
        x1 = 75 + i * segment_width
        svg.append(f'<line x1="{x1}" y1="{page_height - 330}" x2="{x1 + segment_width - 8}" y2="{page_height - 330}" stroke="{OPTIMIZER_COLORS[method]}" stroke-width="4"/>')
    svg.append(f'<text x="75" y="{page_height - 295}" fill="{muted}" opacity="0.72" font-family="Helvetica,Arial,sans-serif" font-size="15" letter-spacing="1.8">{objective.upper()} · {steps} STEPS · {step_length:g}× STEP LENGTH  </text>')
    svg.append(f'<line x1="75" y1="{page_height - 272}" x2="{page_width - 75}" y2="{page_height - 272}" stroke="{ink}" opacity="{theme["rule_opacity"]}"/>')
    positions = [(75, page_height - 238), (75, page_height - 176), (75, page_height - 114),
                 (page_width / 2 + 25, page_height - 238), (page_width / 2 + 25, page_height - 176), (page_width / 2 + 25, page_height - 114)]
    for method_index, (method, (x, y)) in enumerate(zip(methods, positions)):
        c = OPTIMIZER_COLORS[method]
        svg.append(_trajectory_marker(x + 10, y - 5, method_index, c, paper, 4.2, 1.0))
        svg.append(f'<text x="{x + 27}" y="{y}" fill="{c}" font-family="Helvetica,Arial,sans-serif" font-weight="700" font-size="15" letter-spacing="0.8">{method.upper()}</text>')
        for line_index, equation in enumerate(equations[method]):
            svg.append(f'<text x="{x + 27}" y="{y + 21 + line_index * 16}" fill="{ink}" opacity="0.9" font-family="Georgia,Times New Roman,serif" font-style="italic" font-size="13.2">{equation}</text>')
    svg.extend([f'<line x1="75" y1="{page_height - 72}" x2="{page_width - 75}" y2="{page_height - 72}" stroke="{ink}" opacity="{theme["rule_opacity"]}"/>',
                f'<text x="75" y="{page_height - 41}" fill="{muted}" opacity="0.72" font-family="Helvetica,Arial,sans-serif" font-size="11.5" letter-spacing="0.8">gₜ = ∇L(θₜ)  ·  NORMALIZED DEM COORDINATES</text>',
                f'<text x="{page_width / 2 + 25:g}" y="{page_height - 41}" fill="{muted}" opacity="0.72" font-family="Georgia,Times New Roman,serif" font-style="italic" font-size="12">m̂ₜ = mₜ/(1−β₁ᵗ)  ·  v̂ₜ = vₜ/(1−β₂ᵗ)</text>', '</svg>'])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(svg), encoding="utf-8")
    return output
