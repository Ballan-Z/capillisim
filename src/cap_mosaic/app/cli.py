"""Designer CLI (Milestone 1).

Turn a target image into a cap plan, a bill of materials, and distance previews:

    python -m cap_mosaic.app.cli design --image face.jpg --frame 1300x1000 \
        --out plans/face.capproj.json --preview-dir previews

Sizing is given exactly one of: --frame WxH (mm), --caps-across N, or --count N.
With no --image, a built-in demo image is used so the pipeline is runnable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from ..core.geometry import (
    Cap,
    Grid,
    grid_for_caps_across,
    grid_for_count,
    grid_for_frame,
)
from . import planner_designer as designer


def _build_grid(args, aspect_ratio: float) -> Grid:
    cap = Cap(diameter_mm=args.cap_diameter)
    chosen = [bool(args.frame), bool(args.caps_across), bool(args.count)]
    if sum(chosen) != 1:
        raise SystemExit("specify exactly one of --frame, --caps-across, --count")
    if args.frame:
        w, h = (float(v) for v in args.frame.lower().split("x"))
        return grid_for_frame(w, h, cap)
    if args.caps_across:
        return grid_for_caps_across(args.caps_across, aspect_ratio, cap)
    return grid_for_count(args.count, aspect_ratio, cap)


def cmd_design(args) -> None:
    if args.image:
        image = Image.open(args.image).convert("RGB")
    else:
        image = designer.demo_image()
        print("no --image given; using built-in demo image")

    aspect_ratio = image.width / image.height
    grid = _build_grid(args, aspect_ratio)
    title = Path(args.image).stem if args.image else "demo"
    plan = designer.plan_from_image(image, grid, title=title)

    print(f"\nPlan '{plan.title}'")
    print(f"  frame      : {plan.width_mm:.0f} x {plan.height_mm:.0f} mm")
    print(f"  cap size   : {plan.cap_diameter_mm:.0f} mm")
    print(f"  total caps : {plan.count}  ({grid.rows} rows)")
    print("  bill of materials (caps per color):")
    for name, n in plan.bill_of_materials().items():
        print(f"    {name:<8} {n}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        plan.save(args.out)
        print(f"  saved plan -> {args.out}")

    if args.preview_dir:
        out = Path(args.preview_dir)
        out.mkdir(parents=True, exist_ok=True)
        mosaic = designer.render_mosaic(plan, px_per_mm=args.px_per_mm)
        mosaic.save(out / f"{plan.title}_mosaic.png")
        for d in args.distances:
            designer.simulate_distance(mosaic, args.px_per_mm, d).save(
                out / f"{plan.title}_at_{d:g}m.png"
            )
        print(f"  saved previews -> {out}/ (mosaic + distances {args.distances})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cap-mosaic", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("design", help="image -> plan + BOM + previews")
    d.add_argument("--image", help="target image (defaults to a demo image)")
    d.add_argument("--frame", help="frame size in mm as WxH, e.g. 1300x1000")
    d.add_argument("--caps-across", type=int, help="number of caps across the width")
    d.add_argument("--count", type=int, help="approximate total cap count")
    d.add_argument("--cap-diameter", type=float, default=32.0, help="cap diameter mm")
    d.add_argument("--out", help="write the plan project file (.capproj.json)")
    d.add_argument("--preview-dir", help="directory for preview PNGs")
    d.add_argument("--px-per-mm", type=float, default=4.0, help="preview resolution")
    d.add_argument(
        "--distances",
        type=float,
        nargs="*",
        default=[1.0, 3.0, 6.0],
        help="viewing distances (m) to simulate",
    )
    d.set_defaults(func=cmd_design)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
