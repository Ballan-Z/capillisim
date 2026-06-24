# Data Model — the cap dataset / inventory store

Date: 2026-06-24. Status: schema **v1**. Code: `src/cap_mosaic/data/store.py`.

The capture loop produces a growing set of caps, each with several
colour-corrected crops, a measured colour, a quality signal, and — later —
brand/logo features. The original `labels.csv` was throwaway scaffolding; the
real store is **SQLite** (`<dataset>/caps.db`).

## Why SQLite

- **Single file, zero dependencies** (`sqlite3` is in the Python stdlib) and
  available on a phone later — fits the portable-core goal.
- **Normalised + queryable.** One cap has many crops and many embeddings; a flat
  CSV can't hold that without losing data (the CSV stored only one colour per
  cap and dropped the per-frame reads).
- **Evolvable.** Schema version lives in `PRAGMA user_version`; `_MIGRATIONS`
  upgrades an older file in place. Opening a file *newer* than the code errors
  loudly rather than corrupting it.
- **Crops stay as files.** We store each crop's path + SHA-256, never the image
  bytes — the DB stays small and backup/inspection-friendly.

## Schema (v1)

```
cap            one physical cap and its measured colour
 ├─ id            INTEGER PK
 ├─ captured_at   TEXT  (ISO-8601 UTC)
 ├─ r,g,b         INTEGER          true measured colour (no palette bucketing)
 ├─ lab_l,a,b     REAL             derived CIELAB (perceptual matching/clustering)
 ├─ color_std     REAL  nullable   spread across frames = glare/outlier signal
 ├─ n_frames      INTEGER
 ├─ source        TEXT             e.g. 'card_capture', 'labels.csv'
 ├─ brand         TEXT  nullable   future logo/brand label
 └─ notes         TEXT  nullable

frame          one colour-corrected crop (≈5 per cap)
 ├─ id           INTEGER PK
 ├─ cap_id       INTEGER FK → cap.id  (ON DELETE CASCADE)
 ├─ frame_index  INTEGER
 ├─ path         TEXT              relative crop path
 ├─ r,g,b        INTEGER nullable  this frame's glare-masked read
 ├─ lab_l,a,b    REAL   nullable
 ├─ glare_frac   REAL   nullable
 └─ sha256       TEXT   nullable   content hash (integrity / dedup)

embedding      future brand/logo or colour features (kept separate so the
 ├─ cap_id       INTEGER FK → cap.id   core schema doesn't churn when added)
 ├─ model        TEXT
 ├─ dim          INTEGER
 ├─ vec          BLOB              float32 little-endian
 ├─ created_at   TEXT
 └─ PRIMARY KEY (cap_id, model)

meta           dataset-level key/value (name, calibration ref, …)
```

## Key decisions baked in

- **True colour, no bucketing.** Capture stores measured RGB/Lab only; mapping
  caps to painting colours is a per-painting decision at plan time
  (`docs/COLOR_MATCHING.md`).
- **Robust per-cap colour.** The cap's `r,g,b` is the **median across all saved
  frames'** glare-masked reads, so one glary frame can't skew it (this is what
  the old single-frame CSV value got wrong). `color_std` records the spread as a
  built-in quality flag.
- **A cap is one physical cap.** Inventory counts and "how many blue caps do I
  have" are *queries*, not stored buckets — consistent with the open-ended,
  random cap supply.

## API (`cap_mosaic.data.store`)

```python
from cap_mosaic.data.store import CapDataset, FrameRecord

with CapDataset("dataset/caps.db") as db:
    db.add_cap((67, 122, 150), frames=[FrameRecord(0, "crops/cap_0000_f0.png", rgb=(67,122,150))],
               captured_at="2026-06-24T12:00:00", source="card_capture")
    colors = db.colors()          # [(r,g,b), …] — inventory for palette k-means
    caps   = db.caps(with_frames=True)
    db.add_embedding(cap_id, "clip-v1", vec, created_at=...)   # future
```

Consumed by the planner via `planner_designer.inventory_from_db` /
`load_inventory` (which also reads a legacy `.csv`). `import_labels_csv` migrates
an old dataset into the DB.

## Migration path

- **v1 (now):** colour dataset + crops + quality + embedding table (unused yet).
- **Later:** populate `embedding` for brand/logo ID; add per-cap `placed`/build
  state if the store ever also tracks a live build (today that lives in the
  `.capproj.json` plan). Add columns via a new entry in `_MIGRATIONS`.
