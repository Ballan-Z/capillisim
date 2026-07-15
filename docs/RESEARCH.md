# Research: cap datasets + mosaic/build techniques

Two tracks: downloadable cap-image datasets that could grow the colour inventory
(`caps.db`), and photomosaic / assembly techniques worth adopting. Background for
the dithering, the inventory gap report, and the projector stencil / per-colour
passes.

> Licensing caveat: images.cv's free datasets are **personal / non-commercial
> only**: fine for a private colour inventory, a problem only if the project is
> ever distributed. Roboflow/Kaggle sets carry per-dataset licenses; check the
> badge before redistributing.

## Datasets

Ranked by usefulness for extracting cap **colours** (colour/material variety beats
brand-label precision; larger + more visually diverse sets rank higher).

1. **images.cv: Bottlecap Image Classification Dataset**, https://images.cv/dataset/bottlecap-image-classification-dataset; ~1,300 images; free tier *personal/non-commercial only* (https://images.cv/terms-of-service); auth: free signup, direct ZIP (no API); how we'd use it: largest grab-and-go set of isolated cap photos; batch each through our Hough/contour disc crop (`cap_crop`), extract dominant CIELAB colour, bulk-insert into `caps.db` to seed a broad inventory fast.
2. **Roboflow Universe: bottle-cap color classification**, https://universe.roboflow.com/bottle-cup-detection-gnira/bottle-cap-color-classification; ~138 images, 8 classes; open-source (check per-dataset badge; usually CC BY 4.0); auth: free Roboflow account / `roboflow` API key; how we'd use it: already colour-labelled, so a cheap ground-truth check for our dominant-colour extractor before trusting `caps.db`.
3. **Roboflow Universe: Bottles-video (bottlesandcaps)**, https://universe.roboflow.com/bottlesandcaps/bottles-video; ~542 images; open-source; auth: free Roboflow account / API; how we'd use it: video-derived frames give many caps under varied lighting/angles; harvests many colour samples per physical cap, improving glare robustness of the colour reader.
4. **Roboflow Universe: search "bottle cap" (aggregator)**, https://universe.roboflow.com/search?q=class%3Abottle+caps; dozens of community sets (34–500+ images each); mixed open-source licenses; auth: free Roboflow account / API; how we'd use it: one query surfaces many small sets to cherry-pick and merge for maximum colour diversity in a single import run.
5. **Kaggle: bottle cap classification (tahuuanh)**, https://www.kaggle.com/datasets/tahuuanh/bottle-cap-classification; brand-classification set; Kaggle license (check page); auth: Kaggle account + `kaggle` API token (`KAGGLE_USERNAME` + `KAGGLE_KEY` in a gitignored `.env`); how we'd use it: brand-organised folders group caps, so extract one representative colour per brand and tag `caps.db` rows with a brand hint alongside the colour.
6. **Kaggle: BOTTLE CAP DATASET (magapuabhijit)**, https://www.kaggle.com/datasets/magapuabhijit/bottle-cap-dataset; smaller supplemental set; Kaggle license; auth: Kaggle account + API; how we'd use it: secondary top-up; same crop-and-extract pipeline to fill colours missing from primary sets.

Also (lower priority, no signup; clone directly for a quick offline pipeline test):
GitHub **s-esposito/CV-DetectTheBottleCap** https://github.com/s-esposito/CV-DetectTheBottleCap and **farhan0715/Bottle-Bottle-Cap-Detection-System** https://github.com/farhan0715/Bottle-Bottle-Cap-Detection-System.

## Techniques

- **Coarse-grid error-diffusion dithering (Floyd–Steinberg in LAB)**, https://en.wikipedia.org/wiki/Floyd%E2%80%93Steinberg_dithering: after quantizing the target to our small cap palette at the coarse cap-grid resolution, diffuse each cell's quantization error to neighbouring *cells* (not sub-pixels). Flat nearest-colour mapping bands badly with few colours; error diffusion trades one solid wrong colour for a mix of adjacent caps the eye blends at distance, so gradients/skin tones read far better. Do it in CIELAB so error is perceptual.
- **MakeBead: inventory-aware dithering + Max-Colors slider**, https://makebead.com/: matches every pixel to a real, finite bead inventory, exposes a "Max Colors" slider (5–50) and an optional Floyd–Steinberg toggle. Mirror this: cap palette size to what's on hand, make dithering a toggle, and match against the *actual owned set*, exactly our inventory constraint.
- **Perceptual tile matching in CIELAB + CIEDE2000**, https://github.com/MorganGrundy/MosaicMagnifique , https://github.com/emersion/jalette , https://danielballan.github.io/photomosaic/docs/ : these generators all score matches with CIEDE2000 in CIELAB, validating our `core/palette.py`. Worth copying: precompute each cap's LAB once and match with a vectorized CIEDE2000 distance matrix (caps × cells) in one pass.
- **Photomosaic tile-selection with a repeat/availability constraint**, https://github.com/Enigma-52/PhotoMosaic , https://codebox.net/pages/photo-mosaic-image-maker : standard tools solve "assign best tile per cell from a library," optionally forbidding tile overuse. That's our matcher + inventory limit: adopt an assignment that decrements cap stock as cells fill so a plan never asks for more of a colour than you own. (The app does the have/need/short report; a hard-constrained plan is the natural next step.)
- **Projector-guided, one-colour-at-a-time assembly (paint-by-number murals)**, https://pbnify.com/paint-by-number-murals , https://www.wallmurals123.com/painting-wall-murals-projector-method.html : muralists project the design and fill one colour at a time with other layers toggled off. Directly validates our per-colour projector pass: light every empty slot for the colour currently in hand; "light colours first" is a nice ordering heuristic.
- **Dithering-kernel selection (Atkinson vs Floyd–Steinberg vs ordered)**, https://www.ascii-magic.com/blog/complete-guide-to-dithering: Atkinson diffuses only 3/4 of the error → higher contrast, fewer muddy cells, often better for a *very* small palette (our case). Future: make the kernel a config option and preview both.
