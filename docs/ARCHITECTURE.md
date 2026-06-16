# Architecture

## Guiding principle: portable core, swappable shell

The POC runs on a PC with a phone as camera. The long-term goal is phone-only.
To make that migration cheap, all logic that has no I/O dependency lives in a
**portable core** (`src/cap_mosaic/core/`): geometry, planning, color/palette,
and matching. Everything device-specific — camera capture, projector output,
calibration UI — lives in **shell** modules (`vision/`, `procam/`, `app/`) that
can be replaced when we move to the phone without touching the core.

```
                +-------------------- PC (POC) --------------------+
 phone camera   |  vision/         core/            procam/        |   projector
 (MJPEG over -->|  cap_reader  -->  matcher    -->   render   ----->|--> (HDMI,
  Wi-Fi)        |  (color)          (best slot)      (highlight)    |    top-down)
                |       ^             ^   |                          |
                |       |         planner |  plan/state (JSON)       |
                |    brand(later)   palette  geometry                |
                +--------------------------------------------------+
```

## Components

### core/ — portable, pure Python, no I/O
- **geometry** — hexagonal cap packing, grid layout, conversions between
  table millimetres and cell indices. A cap is ~32 mm outer diameter (param).
  Hex packing (~91% area coverage) gives the densest, most natural layout.
- **palette** — color-space conversions (sRGB ↔ Lab), perceptual distance
  (CIEDE2000), and binning an arbitrary color to the nearest achievable cap
  color. The palette is open-ended; achievable colors are the bins we can fill.
- **planner** — turns a target image into a `GridPlan`. Inputs in either
  direction: frame size (mm) → cap count, or cap count / caps-across → frame
  size. Steps: compute the hex grid, sample the image per cell, quantize each
  cell to the palette, emit per-cell target colors + table positions. Also
  produces a **bill of materials** (caps needed per color).
- **matcher** — given a recognized cap color and the current state (which cells
  are filled and the target color of each empty cell), return the best empty
  cell by perceptual distance, or **reject** if the best distance exceeds a
  threshold ("set this cap aside"). Greedy for the POC; scarcity-aware
  assignment is a later enhancement (don't spend a rare color on a cell a common
  cap could fill).
- **plan** — the project file: `GridPlan` + filled/empty state, serialized to
  JSON so a build can stop and resume across sessions. This is what makes
  "build in stages" work.

### vision/ — PC shell: see the cap
- **cap_reader** — detect the cap circle (Hough/contour), then read its color
  robustly: convert to HSV/Lab, mask specular glare highlights (metallic caps
  reflect the projector and room lights), and take a median over the cap face.
  Read the cap **off to the side**, out of the projector beam, so the projection
  doesn't contaminate the color.
- **brand** — (deferred) logo/brand classifier. Stubbed to return `None` for the
  POC; when built it refines matching and enables "place this specific cap"
  designs. Architected as an optional signal layered on top of color.

### procam/ — PC shell: project the guidance
- **calibrate** — establish the homography between table millimetres and
  projector pixels so we can draw any cell at the correct real-world size and
  position. POC approach: project a known rectangle / 4 corner markers, align to
  a taped reference of known size (or measure with a tape and enter dimensions);
  compute scale + keystone. Enhancement: auto-calibrate with ArUco markers seen
  by the phone camera.
- **render** — a fullscreen window on the projector output. Optionally shows a
  faint full template; always highlights the single chosen cell with a glowing /
  pulsing marker, placed via the calibration homography.

### app/ — orchestration
- **cli** — the offline designer: image in → `GridPlan` + BOM + distance-preview
  PNGs.
- **build_loop** — the interactive loop: grab a frame from the phone → recognize
  → match → highlight → wait for placement confirmation → mark filled → persist →
  repeat. POC confirmation is manual (keypress/button); camera auto-verify is a
  later enhancement.

## Phone → PC camera transport (POC)

No custom mobile app needed: a standard IP-webcam app streams MJPEG over Wi-Fi
and OpenCV reads the URL. In the phone-only future this collapses into a single
device and the transport disappears.

## Sizing & viewing-distance math

Two independent knobs decide whether a piece "reads":

1. **Recognizability** — how many caps span the subject. A face needs very
   roughly 30–50 caps across to be identifiable. This sets the grid resolution.
2. **Blending distance** — caps merge into tones when each cap subtends a small
   enough angle to the eye (human acuity ≈ 1 arcminute). Larger caps ⇒ stand
   further back.

Rather than commit to a fragile magic constant for "good viewing distance," the
designer ships a **distance simulator**: render the planned mosaic, then Gaussian
-blur it with a sigma matching eye resolution at distance D, with D adjustable.
The user *sees* "from 2 m vs 6 m" and picks the trade-off directly. This is also
how we answer "pattern up close vs portrait from afar" without guesswork.

Projection sharpness check: a 1080p projector over a ~1 m table is ~0.5 mm/pixel,
far finer than a 32 mm cap, so highlight edges are crisp.

## Persistence & staged builds

Every build is a project file (JSON): the plan, the palette/BOM, and which cells
are filled. You can close the laptop and resume weeks later as more caps arrive —
the core requirement that the mosaic is built in stages.
