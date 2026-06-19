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
