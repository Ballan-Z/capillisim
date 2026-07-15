# Project status

Where the project stands: what's built and tested, and what still needs the
physical rig. The full milestone plan is in `docs/ROADMAP.md`.

## Built and tested (headless)

**Designer / core** (`core/`, `app/planner_designer.py`)
- Image → `GridPlan` with a CIELAB k-means palette, curated presets
  (portrait/sunset/space), reject-gate holes, bare-white background holes.
- Thin-outline detect + thicken (`core/features.py`) so ~1-cap strokes survive.
- **Dither** (`core/dither.py`): CIELAB Floyd–Steinberg error diffusion over the
  cap grid; a small palette reads far better on gradients/tones.

**Estimator web app** (`app/webapp/`, see `docs/ESTIMATOR.md`)
- size ↔ distance solve, legibility floor, minimal size, effective colours.
- Distance sim = shrink-in-fixed-FOV, stay sharp, linear-light cap blending.
- Cap rendering: uniform auto-cropped real caps (`app/cap_crop.py`) + procedural,
  glued on a controllable **board colour**; region crop; colour isolate.
- **Hold-to-compare** original vs caps (`/target`); **printable cap map** PDF
  (`app/cap_map.py`, `/capmap`); **inventory gap** report from `caps.db`
  (have/need/short).
- **Judges**: heuristic cap-art check (`core/critique.py`) + a Qwen vision judge
  (`app/llm_judge.py`); an owned-palette AI prompt (`/palette_prompt`) and an
  experimental image simplify (`app/ai_edit.py`).
- **Build from my caps**: duplicates pooled by ring signature
  (`app/cap_stock.py`), greedy global ΔE00 assignment (`core/assign.py`), and
  inventory patterns (`core/pattern.py`, `/pattern`).

**Projector build** (`procam/render.py`, `app/project_plan.py`)
- **Stencil** (`render_stencil`): every cell lit in its cap colour at 1:1, plus a
  **per-colour pass** (light one colour at a time: glue it, then the next).
- `project_plan` entrypoint with S/C/N/P/Q keys; display + keys injected as
  callables (headless-tested); `main` drives the real fullscreen projector.
- Interactive per-cap placement loop (`build_loop.run_loop`).

**Cap scanning** (`app/cap_capture.py`, `app/make_card.py`): card-based capture
into `caps.db` with median colour + a busy-ness quality signal.

## Pending (needs the rig)

- On-rig projector calibration (`from_correspondences`) and a live
  stencil / per-colour verification — the projection code is done but untested on
  a real board.
- Live phone stream for the interactive loop (the snapshot path works today).
- Threshold tuning on real caps (reject ΔE, dither kernel, inventory tolerance).
- Growing `caps.db` with more scanned caps for broader real-cap colour coverage
  (see the dataset notes in `docs/RESEARCH.md`).
