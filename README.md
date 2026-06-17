# DEM Optimizer Art

Generate print-ready SVG wall art from a real digital elevation model (DEM), with trajectories for SGD, Momentum, NAG, AdaGrad, RMSProp, and Adam.

The terrain becomes the loss function. Every optimizer starts at the same visible point and follows the measured surface toward a basin. The poster title is the DEM name, and the legend equations exactly match the implemented update rules.

## Quick start

Python 3.10+ is required. CSV input and SVG output have no third-party dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
dem-art examples/ngorongoro.json
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
dem-art examples/my-landscape.json
```

## Choosing start points visually

`start_points` uses image-like normalized coordinates. `[0,0]` is the back-left of the DEM, `[1,1]` is the front-right, and `[0.5,0.5]` is its centre. Every point is drawn as a labelled circle on the surface.

```json
"start_points": [[0.65, 0.40], [0.25, 0.72]]
```

Experiment without editing JSON:

```bash
dem-art examples/ngorongoro.json --steps 40 --start 0.65,0.40 --start 0.30,0.75
```

## Configuration

| Setting | Meaning |
|---|---|
| `title` | DEM name used as the chromatic poster title |
| `dem` | CSV, GeoTIFF, PNG, or JPEG elevation grid |
| `steps` | Number of updates per optimizer |
| `start_points` | One or more `[x,y]` points in the visual `0..1` coordinate system |
| `optimizers` | Any subset of `SGD`, `Momentum`, `NAG`, `AdaGrad`, `RMSProp`, `Adam` |
| `palette` | `spectrum`, `ocean`, `magma`, `mono`, or a JSON list of hex colours |
| `smoothing` | Low-pass passes; `6–12` works well for noisy real terrain |
| `grid_lines` | Coloured wire density |
| `vertical_scale` | Visual height exaggeration |
| `fill_opacity` | Transparent colour wash beneath the wireframe |
| `png_preview` | Also create a PNG when a converter is available |

A custom colour map is simply:

```json
"palette": ["#172a46", "#007f86", "#f4d35e", "#ee6352"]
```

CLI values override the JSON when supplied:

```bash
dem-art examples/yosemite.json --dem data/my-dem.tif --palette magma --steps 35 --output output/custom.svg
```

## Included examples

- Ngorongoro Crater: broad, smooth basin and clean optimizer separation.
- Mount St Helens: stronger momentum and NAG overshoot.
- Yosemite Valley: elongated valley with multiple starting points.

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

