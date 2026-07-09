# Work log — caps-own-fit

Plan: plans/caps-own-fit-plan.md
Mode: autonomous, Opus/High. Local only (no subagents). Branch: main.

Frozen contracts:
- `usable_groups(groups, image, threshold_de, filter_k) -> list[Group]`
- `fit_caps_across(n_caps: int, aspect: float) -> int`
- `own_threshold: float` (ΔE00, default 12) on /estimate + /simulate

## Step 1 — Reproduce & confirm diagnosis (read-only) — DONE
Scratch: $CLAUDE_JOB_DIR/tmp/step1_diag.py, step1_sim.py

Diagnosis: grid sized by size slider ≫ owned caps.
- owned caps: 416, colour groups: 214
- caps_across=40 → 1817 cells, 416 filled, 1401 holes (77%), 214 distinct colours
- caps_across=80 → 7314 cells, 416 filled, 6898 holes (94%), 214 distinct
- caps_across=120 → 16491 cells, 416 filled, 16075 holes (97%), 214 distinct
- /simulate from_my_caps → HTTP 200, image/png, 308 KB (NOT a render miss)
- /estimate from_my_caps → colors_used=214 (all groups → noise), total_caps=416

Root cause confirmed: cells ≫ 416, distinct colours in the hundreds, high hole
fraction. `assign_stock` fills only ~416 cells, rest are noise/holes.
Commit: skipped (read-only).

## Step 2 — RED tests for the fit algorithm — DONE
File: tests/test_owned_fit.py (new). 4 tests.
- test_fit_caps_across_within_tolerance: grid count within ±12% of n (n=150/300/416).
- test_usable_groups_threshold_crossover: far group (ΔE~20.7) excluded at thr=12,
  included at thr=40; near group always kept.
- test_usable_groups_monotone_nondecreasing: |usable(thr)| non-decreasing.
- test_fit_path_uses_few_colours_and_fills_X_cells: fit path uses ≤ usable groups
  (3, not 6) distinct colours, fills ~X cells.
Validation: RED — ImportError (fit_caps_across / usable_groups absent). Expected.
Note: naive analytic fit undershoots for small n; Step 3 uses a small search
around the analytic estimate (within 12% for realistic X ≥ ~120).
Commit: test: Step 2 - red tests for caps-I-own fit algorithm

## Step 3 — GREEN: usable_groups + fit_caps_across — DONE
File: src/cap_mosaic/app/planner_designer.py
- usable_groups(groups, image, threshold_de, filter_k): filter_k CIELAB k-means
  centroids = colours the image needs; keep groups whose min ΔE00 (ciede2000_matrix)
  to any centroid <= threshold_de. Monotone, order-preserving.
- fit_caps_across(n_caps, aspect): analytic inverse of hex count, then small
  search window (est-4..est+7) for the caps-across whose real grid.count is
  closest to n_caps (closed form undershoots at edges).
Imports: added HEX_CELL_AREA_FACTOR, Cap, grid_for_caps_across.
Validation: test_owned_fit 4/4 pass; full suite 281 passed, 0 failed.
Commit: feat: Step 3 - usable_groups + fit_caps_across (green)

## Step 4 — Wire into the server — DONE
Files: src/cap_mosaic/app/webapp/server.py, tests/test_inventory_browser.py
- _plan(from_my_caps): now usable_groups(groups, img, own_threshold, filter_k=
  max(colors,16)) -> fit_caps_across(X, aspect) -> grid shrunk to usable-cap count
  -> plan_from_inventory over kept groups. Fallback to full stock if threshold
  excludes everything. own_threshold added to cache key.
- _own_geometry(res, plan): fitted piece overrides slider size (caps_across,
  width_mm, height_mm); panel_caps = plan.count; stock_used gains "usable".
- /estimate + /simulate gain own_threshold (ΔE00, default 12), passed through.
Validation (real caps.db, 2-tone image, size 3000):
  thr=6  colors_used=3  caps_across=2  panel=3   total=3   holes=0  (was 214/thousands/77-97% holes)
  thr=12 colors_used=15 caps_across=5  panel=23  total=21  holes=2
  thr=20 colors_used=75 caps_across=10 panel=105 total=103 holes=2
  Colours/size now scale with the slider; holes ~0; image reads.
Tests: test_own_threshold_filters_colours_and_fits_grid,
  test_own_threshold_simulate_renders. Full suite 283 passed, 0 failed.
Commit: feat: Step 4 - server: own_threshold + fit resolution for caps-I-own
