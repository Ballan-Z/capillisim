# Prior Art Review

Date: 2026-06-15. Purpose: determine whether the proposed system is novel, and
what existing work we can reuse rather than reinvent.

## Summary verdict

The **mosaic-generation** half of the idea is well-trodden and we should reuse
known techniques rather than invent them. The **interactive build loop** —
showing an arbitrary cap to a phone camera, having software decide where it goes
(or reject it), and a projector highlighting that exact slot at 1:1 scale — does
**not** appear to exist as an integrated system for mosaics. That integration is
the novel contribution.

## What already exists

### Mosaic / bottle-cap art generation — solved
- **"Structure-aware bottle cap art"** (academic, Computers & Graphics 2022,
  ScienceDirect S0097849322001510). Fully automatic. Input: an image, a set of
  caps with their colors and quantities, and the desired number of caps across
  the horizontal extent; output: a ~1 m-scale cap layout. Considers image
  structure/edges, not just per-pixel color. This is effectively the
  state-of-the-art generator and a strong reference for our planner.
- **Open Source Beer Bottle Cap Mosaic Program** (Instructables). Evaluates each
  tile by color, contrast, and internal marking, across all rotations.
- **Roy Feinson** and many Etsy/Pinterest artists produce cap mosaics by hand.
- General **bead-art / cross-stitch pattern generators** solve the same
  palette-quantization problem.

### Static projector tracing — common DIY technique, but manual
- The standard hobby method: project the target image onto plywood and arrange
  caps by eye. No per-cap guidance, no camera, no scale guarantee.

### Projection-based assembly guidance — exists, but industrial (not mosaics)
- **smARt.Assembly** and **Twin Coast Metrology Assembly Assistant** project
  work instructions / part locations onto a work area to cut assembly defects.
  This is the closest analog to our interactive loop, but aimed at factory
  assembly, not art and not arbitrary-cap matching.

### AR mosaic visualization — exists, but for shopping/preview
- **Mozaico AR** and **Houzz** tile AR let you preview a finished mosaic in a
  room. Visualization only; no assembly guidance.

## The gap we fill (novelty)

No existing system combines all three of:
1. **Cap-in-hand recognition** via a phone camera of an *arbitrary* cap.
2. **Partial-inventory matching** — decide the best remaining empty slot for the
   cap you happen to be holding, or reject it ("doesn't help this piece").
3. **Projector 1:1 highlighting** of the exact target cell so you place it
   without measuring.

as a single interactive, incremental build loop. That is the part worth
building and the part that is plausibly original.

## Sources
- https://www.instructables.com/Open-Source-Beer-Bottle-Cap-Mosaic-Program/
- https://www.sciencedirect.com/science/article/abs/pii/S0097849322001510
- https://www.researchgate.net/publication/304055186_smARtAssembly_-_Projection-Based_Augmented_Reality_for_Supporting_Assembly_Workers
- https://www.mdpi.com/2076-3417/10/3/796
- https://twincoastmetrology.com/products/projection/software/
- https://www.mozaico.com/blogs/news/the-future-of-mosaic-shopping-explore-visualize-and-buy-with-our-new-ar-app
- https://royfeinson.com/bottle-cap-mosaics/
