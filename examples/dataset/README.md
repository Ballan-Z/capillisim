# Example cap dataset

This is a **~100-cap sample** — a colour-diverse slice of a real scan, one crop
per cap. It exists so Capillisim is playable the moment you clone: the app falls
back to it whenever you haven't scanned your own caps yet, so the shopping list,
patterns and "build from my stock" all have real caps to work with.

It is **not** the real thing. The moment you scan caps into `dataset/` (at the
repo root), that inventory takes precedence and this sample is ignored. See
[../../docs/BUILD_DATASET.md](../../docs/BUILD_DATASET.md).

Provided for demo use, under the repo's [MIT license](../../LICENSE).

Regenerate from a full `dataset/`: `python tools/build_example_dataset.py`.
