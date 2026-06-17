from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from .dem import prepare_surface
from .render import PALETTES, render


def _preview(svg: Path, png: Path) -> None:
    try:
        import cairosvg
        cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=1200, output_height=1600)
    except ImportError:
        if shutil.which("sips"):
            subprocess.run(["sips", "-s", "format", "png", str(svg), "--out", str(png)], check=True,
                           stdout=subprocess.DEVNULL)
        else:
            print("PNG skipped; install dem-optimizer-art[preview]. The SVG is complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn any DEM into optimizer trajectory wall art.")
    parser.add_argument("config", type=Path, help="JSON configuration file")
    parser.add_argument("--dem", type=Path, help="Override DEM path")
    parser.add_argument("--output", type=Path, help="Override SVG output")
    parser.add_argument("--steps", type=int, help="Override optimizer step count")
    parser.add_argument("--start", action="append", metavar="X,Y", help="Start point in visual 0..1 coordinates; repeatable")
    parser.add_argument("--palette", choices=tuple(PALETTES), help="Override colour map")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base = config_path.parent
    dem_path = args.dem or (base / config["dem"])
    output = args.output or (base / config.get("output", "output/art.svg"))
    if args.steps is not None: config["steps"] = args.steps
    if args.palette: config["palette"] = args.palette
    if args.start: config["start_points"] = [[float(v) for v in item.split(",")] for item in args.start]
    surface = prepare_surface(dem_path, int(config.get("smoothing", 8)), int(config.get("dem_resolution", 96)))
    svg = render(surface, config, output)
    print(f"Wrote {svg.resolve()}")
    if config.get("png_preview", True):
        png = svg.with_suffix(".png")
        _preview(svg, png)
        if png.exists(): print(f"Wrote {png.resolve()}")


if __name__ == "__main__":
    main()

