from __future__ import annotations

import math

from .dem import Surface


OPTIMIZER_COLORS = {
    "SGD": "#e23b3b", "Momentum": "#f28e2b", "NAG": "#d4b216",
    "AdaGrad": "#2ca25f", "RMSProp": "#2589bd", "Adam": "#7b4ab5",
}

EQUATIONS = {
    "SGD": "θₜ₊₁ = θₜ − ηgₜ",
    "Momentum": "vₜ = βvₜ₋₁ + gₜ  ·  θₜ₊₁ = θₜ − ηvₜ",
    "NAG": "gₜ = ∇L(θₜ − ηβvₜ₋₁)  ·  vₜ = βvₜ₋₁ + gₜ  ·  θₜ₊₁ = θₜ − ηvₜ",
    "AdaGrad": "Gₜ = Gₜ₋₁ + gₜ²  ·  θₜ₊₁ = θₜ − ηgₜ/(√Gₜ+ε)",
    "RMSProp": "vₜ = βvₜ₋₁ + (1−β)gₜ²  ·  θₜ₊₁ = θₜ − ηgₜ/(√vₜ+ε)",
    "Adam": "mₜ = β₁mₜ₋₁+(1−β₁)gₜ  ·  vₜ = β₂vₜ₋₁+(1−β₂)gₜ²  ·  θₜ₊₁ = θₜ−ηm̂ₜ/(√v̂ₜ+ε)",
}

EQUATION_LINES = {
    "SGD": ("θₜ₊₁ = θₜ − ηgₜ",),
    "Momentum": ("vₜ = βvₜ₋₁ + gₜ", "θₜ₊₁ = θₜ − ηvₜ"),
    "NAG": ("gₜ = ∇L(θₜ − ηβvₜ₋₁)", "vₜ = βvₜ₋₁ + gₜ  ·  θₜ₊₁ = θₜ − ηvₜ"),
    "AdaGrad": ("Gₜ = Gₜ₋₁ + gₜ²", "θₜ₊₁ = θₜ − ηgₜ/(√Gₜ+ε)"),
    "RMSProp": ("vₜ = βvₜ₋₁ + (1−β)gₜ²", "θₜ₊₁ = θₜ − ηgₜ/(√vₜ+ε)"),
    "Adam": ("mₜ = β₁mₜ₋₁+(1−β₁)gₜ  ·  vₜ = β₂vₜ₋₁+(1−β₂)gₜ²", "θₜ₊₁ = θₜ − ηm̂ₜ/(√v̂ₜ+ε)"),
}


def equation_lines(objective: str = "descent") -> dict[str, tuple[str, ...]]:
    """Return equations using the same update direction as the renderer."""
    if objective == "descent":
        return EQUATION_LINES
    return {
        "SGD": ("θₜ₊₁ = θₜ + ηgₜ",),
        "Momentum": ("vₜ = βvₜ₋₁ + gₜ", "θₜ₊₁ = θₜ + ηvₜ"),
        "NAG": ("gₜ = ∇L(θₜ + ηβvₜ₋₁)", "vₜ = βvₜ₋₁ + gₜ  ·  θₜ₊₁ = θₜ + ηvₜ"),
        "AdaGrad": ("Gₜ = Gₜ₋₁ + gₜ²", "θₜ₊₁ = θₜ + ηgₜ/(√Gₜ+ε)"),
        "RMSProp": ("vₜ = βvₜ₋₁ + (1−β)gₜ²", "θₜ₊₁ = θₜ + ηgₜ/(√vₜ+ε)"),
        "Adam": ("mₜ = β₁mₜ₋₁+(1−β₁)gₜ  ·  vₜ = β₂vₜ₋₁+(1−β₂)gₜ²", "θₜ₊₁ = θₜ + ηm̂ₜ/(√v̂ₜ+ε)"),
    }


def run(surface: Surface, name: str, start: tuple[float, float], steps: int,
        objective: str = "descent", step_length: float = 1.0) -> list[tuple[float, float]]:
    if objective not in ("descent", "ascent"):
        raise ValueError("objective must be 'descent' or 'ascent'")
    direction = -1 if objective == "descent" else 1
    step_length = max(0.01, float(step_length))
    x, y = start
    vx = vy = sx = sy = mx = my = 0.0
    path = [(x, y)]
    eps = 1e-8
    for t in range(1, steps + 1):
        if name == "NAG":
            gx, gy = surface.gradient(x + direction * step_length * 0.045 * 0.82 * vx,
                                      y + direction * step_length * 0.045 * 0.82 * vy)
        else:
            gx, gy = surface.gradient(x, y)
        if name == "SGD":
            x, y = x + direction * step_length * 0.13 * gx, y + direction * step_length * 0.13 * gy
        elif name in ("Momentum", "NAG"):
            vx, vy = 0.82 * vx + gx, 0.82 * vy + gy
            x, y = x + direction * step_length * 0.045 * vx, y + direction * step_length * 0.045 * vy
        elif name == "AdaGrad":
            sx, sy = sx + gx * gx, sy + gy * gy
            x, y = x + direction * step_length * 0.28 * gx / (math.sqrt(sx) + eps), y + direction * step_length * 0.28 * gy / (math.sqrt(sy) + eps)
        elif name == "RMSProp":
            sx, sy = 0.90 * sx + 0.10 * gx * gx, 0.90 * sy + 0.10 * gy * gy
            x, y = x + direction * step_length * 0.075 * gx / (math.sqrt(sx) + eps), y + direction * step_length * 0.075 * gy / (math.sqrt(sy) + eps)
        elif name == "Adam":
            mx, my = 0.90 * mx + 0.10 * gx, 0.90 * my + 0.10 * gy
            sx, sy = 0.999 * sx + 0.001 * gx * gx, 0.999 * sy + 0.001 * gy * gy
            mhx, mhy = mx / (1 - 0.90**t), my / (1 - 0.90**t)
            shx, shy = sx / (1 - 0.999**t), sy / (1 - 0.999**t)
            x, y = x + direction * step_length * 0.13 * mhx / (math.sqrt(shx) + eps), y + direction * step_length * 0.13 * mhy / (math.sqrt(shy) + eps)
        x, y = max(-2.95, min(2.95, x)), max(-2.95, min(2.95, y))
        path.append((x, y))
    return path


def find_high_disagreement_starts(
    surface: Surface,
    methods: list[str],
    steps: int,
    objective: str = "descent",
    step_length: float = 1.0,
    count: int = 3,
    candidate_grid: int = 11,
) -> list[tuple[float, float]]:
    """Find spatially distinct starts where optimizer paths naturally separate."""
    methods = [name for name in methods if name in OPTIMIZER_COLORS]
    if len(methods) < 2:
        raise ValueError("Select at least two optimizers to measure disagreement")
    if objective not in ("descent", "ascent"):
        raise ValueError("objective must be 'descent' or 'ascent'")
    count = max(1, min(6, int(count)))
    probe_steps = max(6, min(24, int(steps)))
    scored: list[tuple[float, float, float]] = []
    candidates = []

    for row in range(candidate_grid):
        v = 0.14 + 0.72 * row / (candidate_grid - 1)
        for column in range(candidate_grid):
            u = 0.14 + 0.72 * column / (candidate_grid - 1)
            start = (-3 + 6 * u, -3 + 6 * v)
            candidates.append((u, v, start, surface.value(*start)))

    elevations = sorted(candidate[3] for candidate in candidates)
    percentile = 0.65 if objective == "descent" else 0.35
    elevation_cutoff = elevations[round((len(elevations) - 1) * percentile)]
    if objective == "descent":
        eligible = [candidate for candidate in candidates if candidate[3] >= elevation_cutoff]
    else:
        eligible = [candidate for candidate in candidates if candidate[3] <= elevation_cutoff]

    for u, v, start, elevation in eligible:
        paths = [run(surface, method, start, probe_steps, objective, step_length) for method in methods]
        sample_indices = [round((probe_steps - 1) * fraction) for fraction in (0.25, 0.5, 0.75, 1.0)]
        separation = 0.0
        comparisons = 0
        for sample_index, weight in zip(sample_indices, (0.35, 0.55, 0.8, 1.0)):
            for left in range(len(paths)):
                for right in range(left + 1, len(paths)):
                    separation += weight * math.dist(paths[left][sample_index], paths[right][sample_index])
                    comparisons += 1
        separation /= comparisons or 1
        movement = sum(math.dist(start, path[-1]) for path in paths) / len(paths)
        edge_hits = sum(1 for path in paths if max(abs(path[-1][0]), abs(path[-1][1])) > 2.88)
        elevation_span = (elevations[-1] - elevations[0]) or 1.0
        relative_elevation = (elevation - elevations[0]) / elevation_span
        altitude_preference = relative_elevation if objective == "descent" else 1.0 - relative_elevation
        score = separation * (0.65 + 0.35 * min(1.0, movement / 1.2)) * (0.55 ** edge_hits) * (0.85 + 0.15 * altitude_preference)
        scored.append((score, u, v))

    scored.sort(reverse=True)
    selected: list[tuple[float, float]] = []
    for _, u, v in scored:
        if all(math.dist((u, v), point) >= 0.22 for point in selected):
            selected.append((u, v))
            if len(selected) == count:
                break
    if len(selected) < count:
        for _, u, v in scored:
            if (u, v) not in selected:
                selected.append((u, v))
                if len(selected) == count:
                    break
    return selected
