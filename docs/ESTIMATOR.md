# Mosaic Estimator (web app)

Date: 2026-07-01. Code: `src/cap_mosaic/app/webapp/`, `core/estimator.py`,
`core/legibility.py`, `app/cap_render.py`, `app/fake_caps.py`.

A local web app to answer, for any image: **how big must the mosaic be, from how
far is it seen well, and how many caps of each colour does it take** — with a
realistic simulation of how it reads at a chosen size and distance.

## Run

```bash
pip install -e .[web]                      # fastapi, uvicorn, python-multipart
PYTHONPATH=src python -m cap_mosaic.app.webapp     # http://127.0.0.1:8000
```

Drag an image in, pick **Picture** or **Pattern**, then move the **size** and
**viewing-distance** sliders. Buttons solve one axis from the other ("size for
this distance" / "distance for this size").

## The model

Caps are a fixed physical size (~32 mm), so a mosaic is a heavy downsampling of
the target and only reads once you stand far enough that caps blend.

- **Legibility floor** (`core/legibility.py`) — render the image at N caps-across
  and compare structure to the original (windowed SSIM); the smallest N that
  clears a threshold is the minimum caps to represent the subject. Below it the
  app warns: *won't read from any distance*. Detailed images need many more caps
  than simple ones; **Pattern** mode uses a looser threshold (no subject to
  recognise).
- **Size ↔ distance** (`core/estimator.py`) —
  - *size → distance*: caps-across from the width; the **min distance** where
    caps stop being visible (they blend) and the **recommended** distance that
    fills a comfortable field of view;
  - *distance → size*: the width that fills the view at that distance, flagged if
    it falls below the legibility floor.
- **Shades merge with distance** — far away, near colours blend, so the effective
  palette shrinks (`effective_colors`); the app shows *colours used / seen*.
- **Realistic simulation** (`app/cap_render.py`, `app/fake_caps.py`,
  `planner_designer.view_at_distance`, `core/sizing.py`) — the mosaic is tiled
  from actual cap images (real `dataset/caps.db` crops + procedurally generated
  fake caps with rims/logos). To show a viewing distance it is **not** blurred:
  it **shrinks inside a fixed field of view frame and stays sharp**. As it
  subtends fewer pixels, an area-resample done in **linear light** (sRGB→linear→
  area-average→sRGB) merges neighbouring caps — that is physically-correct
  optical colour mixing, so a 50/50 black+white tile averages to the linear
  midpoint (~188), not the sRGB midpoint (~128). `apparent_fraction(width,
  distance, fov)` sets how much of the ~50° frame the piece fills (shown as
  *fills ~X% of your view*). **Close up it fills your view as caps; far away it
  is a small sharp picture in bare board.**
- **Bare-white background** — cells sampled as near-white (all channels ≥
  `white_level`, default 238) are left as **bare board** (holes), not paved with
  white caps. Controlled by `plan_from_image(bare_white=...)`; on by default in
  the app, overridable with `&bare_white=false`.

## Endpoints

- `POST /upload` — image -> `{id, width, height, aspect}`
- `GET /estimate?image_id=&size_mm=|distance_m=&mode=&colors=&bare_white=` -> caps,
  legibility, distances, `bom` (hex -> count), colours used/effective,
  `apparent_pct` (share of field of view filled)
- `GET /simulate?image_id=&size_mm=&distance_m=&mode=&bare_white=` -> cap-rendered
  PNG of the fixed FOV frame: the sharp mosaic shrunk to the size it subtends at
  the distance, surrounded by bare board

## Limitations / next

- SSIM legibility threshold is a heuristic (exposed for calibration on real
  images). Pattern/picture is a manual toggle; recognition comes later.
- Online cap datasets (Kaggle, images.cv) are deferred — they need auth +
  licensing review; the POC uses procedural + captured caps.
- Plan/BOM resolution is capped (`_MAX_CAPS_ACROSS`) to keep the UI responsive.

## Known gaps

The distance model captures shrink + optical (acuity-bounded) blending in linear
light. Left for later:

- **Contrast sensitivity (CSF).** Real acuity depends on contrast, not just
  angular size; a full model would fold in the contrast-sensitivity function.
  We use a fixed acuity (`ACUITY_ARCMIN ≈ 1.5`) as the optical limit.
- **`read_quality` vs optical acuity.** `read_quality` is a coarse
  *perceptual-integration* heuristic (when the brain fuses tiles into a subject),
  a different thing from the optical area-resample; the two are not yet unified.
- **White subject vs white background.** Bare-white holing can't tell a white
  *subject* from a white *background* — it drops both. A subject/background
  segmentation would disambiguate.
- **Gloss & lighting.** Cap gloss, specular highlights, and ambient lighting are
  out of scope; the simulation assumes flat, evenly-lit matte tiles.
