# Gradient Atlas

**Optimization, mapped.**

Generate print-ready SVG wall art from a real digital elevation model (DEM), with trajectories for SGD, Momentum, NAG, AdaGrad, RMSProp, and Adam.

Choose **Descent** to minimize elevation and reach a valley, or **Ascent** to maximize elevation and climb toward a peak. Every optimizer and displayed equation switches direction consistently.

The terrain becomes the loss function. At each visible start point, every selected optimizer follows the same measured surface toward a basin or peak. The poster title is the DEM name, and the legend equations exactly match the implemented update rules.

![Gradient Atlas rendering of optimizer trajectories descending into Ngorongoro Crater](docs/gradient-atlas-ngorongoro.png)

*Ngorongoro Crater with three altitude-constrained, high-disagreement start points.*

## Visual interface

![Gradient Atlas web interface](docs/gradient-atlas-web-ui.png)

Launch the local studio:

```bash
uv run gradient-atlas-ui
```

Alternatively, inside an activated Python virtual environment: `pip install -e . && gradient-atlas-ui`.

It opens at `http://127.0.0.1:8765`. There are three ways to supply terrain:

1. **Search map** — search for a named place, adjust or redraw the selection rectangle, and fetch its elevation.
2. **Coordinates** — enter latitude, longitude, and a 2–200 km coverage radius.
3. **Upload** — drag in an existing CSV, GeoTIFF, PNG, or JPEG DEM.

The first two options fetch global Terrarium elevation tiles from the public AWS Open Data terrain dataset. Tiles are cached under `~/.cache/gradient-atlas/tiles`, so revisiting an area is much faster. Place search runs only when the search button is pressed—not as autocomplete—and is cached and rate-limited in accordance with the public Nominatim usage policy.

After choosing terrain, click its normalized preview to place one or more starting points, choose optimizers and colours, then generate SVG or a 2400×3200 PNG.

Both working previews can be expanded: **Expand terrain** opens a near-full-window start-point editor, while **Expand artwork** opens a large inspection view with download controls. The default terrain editor, source map, and artwork panel are also enlarged for desktop displays.

Artwork updates automatically after terrain regions, start points, optimizer settings, colours, relief, or tile rotation change. Updates are debounced and serialized, so rapid slider and map events produce one current render instead of a backlog. The Generate button remains in the editor header for an immediate manual refresh.

Use **Find high-disagreement starts** to scan the current DEM for one to five spatially separated locations where the selected optimizers naturally produce the most distinct paths. Descent starts are constrained to the upper 35% of candidate elevations; ascent starts use the lower 35%, so each trajectory has meaningful relief available in its intended direction. The search also respects the current step count and step length while penalizing trajectories that simply run into the tile boundary.

The **Featured terrain** menu includes 20 famous landscapes selected for optimizer-friendly elevation geometry: calderas, breached volcanoes, branching canyons, glacial valleys, pyramidal peaks, and multi-ridge massifs. Each preset supplies a tuned centre and coverage radius, then fetches and renders automatically.

Fetched terrain includes geographic dimensions, so relief can use a physical aspect ratio. **Natural aspect** matches elevation range to the selected area's width, **Subtle boost** applies a restrained 1.45× exaggeration, and **Dramatic** applies 3×. Manual mode remains available; uploaded files without geographic metadata use a conservative fallback.

Uploaded DEMs remain entirely on your computer and are processed in a temporary directory. Map and coordinate modes necessarily contact OpenStreetMap/Nominatim for maps and place search, and AWS Open Data for elevation tiles. CSV works without additional packages. For other uploaded formats:

```bash
pip install -e ".[images]"   # PNG and JPEG
pip install -e ".[geotiff]" # GeoTIFF
```

Useful controls include optimizer selection, 5–80 steps, a 0.25×–2× step-length scale, 90° terrain rotation, three trajectory treatments, visual start-point placement, smoothing, line density, vertical exaggeration, colour wash, and dark-mode-friendly palettes such as `aurora`, `ember`, `twilight`, `topo`, and `glacier`. “Flowing ink” preserves every optimizer sample while drawing a restrained spline, hollow step marks, and a directional chevron for a more deliberate wall-art composition. The CLI remains available for repeatable or automated rendering.

### Print sizes and aspect ratios

Choose standard 4:5, 3:4, 2:3, square, A4, A3, or A2 formats, then switch between portrait and landscape. Custom dimensions from 4–60 inches are also supported. The composition reflows around the selected page rather than stretching the terrain, and exported SVG files include physical dimensions for print workflows. PNG export follows the chosen ratio at up to 200 DPI, capped at 40 megapixels to keep browser memory use reasonable.

## Quick start

Python 3.10+ is required. CSV input and SVG output have no third-party dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
gradient-atlas examples/ngorongoro.json
```

The SVG appears in `output/`. On macOS a PNG preview is also generated automatically. On other platforms install the preview extra:

```bash
pip install -e ".[preview]"
```

## Bring your own DEM

Supported inputs:

- CSV: rectangular numeric elevation grid; an optional first row beginning with `#` is ignored.
- GeoTIFF: install with `pip install -e ".[geotiff]"`.
- 16-bit PNG, PNG, or JPEG: install with `pip install -e ".[images]"`.

Copy `examples/template.json`, change `title` and `dem`, then render it:

```bash
cp examples/template.json examples/my-landscape.json
gradient-atlas examples/my-landscape.json
```

## Choosing start points visually

`start_points` uses image-like normalized coordinates. `[0,0]` is the back-left of the DEM, `[1,1]` is the front-right, and `[0.5,0.5]` is its centre. Every point is drawn as a labelled circle on the surface.

```json
"start_points": [[0.65, 0.40], [0.25, 0.72]]
```

Experiment without editing JSON:

```bash
gradient-atlas examples/ngorongoro.json --steps 40 --start 0.65,0.40 --start 0.30,0.75
```

## Configuration

| Setting | Meaning |
|---|---|
| `title` | DEM name used as the chromatic poster title |
| `dem` | CSV, GeoTIFF, PNG, or JPEG elevation grid |
| `steps` | Number of updates per optimizer |
| `step_length` | Multiplier applied to each optimizer's default learning rate |
| `trajectory_style` | `flowing` (layered spline, markers, arrow), `technical` (raw steps), or `minimal` |
| `theme` | `light` for warm paper or `dark` for a dark atlas background with bright grid lines |
| `print_width` / `print_height` | Physical output dimensions in inches; supports portrait, landscape, and square formats |
| `start_points` | One or more `[x,y]` points in the visual `0..1` coordinate system |
| `optimizers` | Any subset of `SGD`, `Momentum`, `NAG`, `AdaGrad`, `RMSProp`, `Adam` |
| `palette` | `spectrum`, `aurora`, `ember`, `twilight`, `topo`, `glacier`, `ocean`, `magma`, `mono`, or a JSON list of hex colours |
| `smoothing` | Low-pass passes; `6–12` works well for noisy real terrain |
| `grid_lines` | Coloured wire density |
| `vertical_scale` | Visual height exaggeration |
| `auto_fit` | Measure and fit each surface into the available vertical poster area |
| `surface_top` / `surface_bottom` | Vertical framing bounds; with print dimensions, the lower bound is derived from the page aspect |
| `fill_opacity` | Transparent colour wash beneath the wireframe; dark theme enforces a brighter minimum |
| `png_preview` | Also create a PNG when a converter is available |

A custom colour map is simply:

```json
"palette": ["#172a46", "#007f86", "#f4d35e", "#ee6352"]
```

CLI values override the JSON when supplied:

```bash
gradient-atlas examples/yosemite.json --dem data/my-dem.tif --palette magma --theme dark --steps 35 --size 20x30 --output output/custom.svg
```

## Included examples

- **Ngorongoro Crater** — descent from three high rim locations into a broad caldera basin.
- **Mount St Helens** — descent from two elevated starts, emphasizing momentum and NAG overshoot around the breached crater.
- **Yosemite Valley** — ascent from two low valley locations toward competing granite walls and ridges.
- **Template** — a complete baseline configuration for your own DEM.

The sample CSV grids are smoothed approximations derived from public terrain elevation tiles. Keep appropriate source attribution when publishing derived artwork.

## Mathematical conventions

The implementation and poster use the same conventions:

- Momentum stores an unscaled gradient accumulator: `vₜ = βvₜ₋₁ + gₜ`, then `θₜ₊₁ = θₜ − ηvₜ`.
- NAG evaluates the gradient at the look-ahead point `θₜ − ηβvₜ₋₁`.
- AdaGrad accumulates squared gradients without decay.
- RMSProp uses an exponential second-moment average.
- Adam uses first and second moments with bias correction.

This is an art and education project, not an optimizer benchmark: learning rates are chosen to produce readable trajectories on normalized terrain.

## Development

```bash
python3 -m unittest discover -s tests
```
