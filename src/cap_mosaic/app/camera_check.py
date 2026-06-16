"""Phone <-> PC connectivity check (the first hardware step).

Confirms the phone's camera is reachable from the PC over the LAN and that the
color pipeline reads caps correctly, *before* wiring up the projector. Uses the
phone IP-webcam app's still-snapshot endpoint, so it needs only Python + Pillow
(no OpenCV).

    # snapshot mode (default, no OpenCV needed):
    python -m cap_mosaic.app.camera_check --url http://192.168.1.42:8080/shot.jpg

    # save what the phone sees, to eyeball framing/lighting:
    python -m cap_mosaic.app.camera_check --url .../shot.jpg --save seen.png

    # continuous MJPEG stream (needs OpenCV + a display):
    python -m cap_mosaic.app.camera_check --stream http://192.168.1.42:8080/video --show

Hold a cap in front of the phone; each sample prints the color it reads and the
nearest palette cap.
"""

from __future__ import annotations

import argparse
import time

from ..core.palette import distance, nearest
from ..vision.cap_reader import grab_snapshot, read_dominant_color


def _report(rgb) -> str:
    cap = nearest(rgb)
    return f"rgb={tuple(rgb)!s:<16} reads as: {cap.name:<7} (dE={distance(rgb, cap):.1f})"


def cmd_snapshot(args) -> None:
    print(f"Connecting to {args.url} ...")
    for i in range(args.samples):
        try:
            img = grab_snapshot(args.url, timeout=args.timeout)
        except Exception as e:  # noqa: BLE001 - surface any network/decoding error plainly
            raise SystemExit(f"could not reach the phone: {e}\n"
                             "Check: same Wi-Fi? app running? URL/IP correct? firewall?")
        rgb = read_dominant_color(img, center_fraction=args.center)
        print(f"  [{i + 1}/{args.samples}] {img.size[0]}x{img.size[1]}  {_report(rgb)}")
        if args.save and i == 0:
            img.save(args.save)
            print(f"        saved first frame -> {args.save}")
        if i < args.samples - 1:
            time.sleep(args.interval)
    print("Link OK." if args.samples else "")


def cmd_stream(args) -> None:  # pragma: no cover - needs OpenCV + camera + display
    try:
        import cv2
    except ImportError:
        raise SystemExit("stream mode needs OpenCV: pip install opencv-python")
    from PIL import Image

    cap = cv2.VideoCapture(args.stream)
    if not cap.isOpened():
        raise SystemExit(f"could not open stream {args.stream}")
    print("Streaming. Press 'q' in the window (or Ctrl-C) to stop.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("dropped frame")
                continue
            rgb = read_dominant_color(
                Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)),
                center_fraction=args.center,
            )
            label = _report(rgb)
            if args.show:
                cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2)
                cv2.imshow("cap reader", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                print("  " + label)
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="cap-mosaic-camera-check", description=__doc__)
    p.add_argument("--url", help="snapshot JPEG endpoint, e.g. http://IP:8080/shot.jpg")
    p.add_argument("--stream", help="MJPEG/RTSP stream URL (OpenCV)")
    p.add_argument("--show", action="store_true", help="show a live window (stream mode)")
    p.add_argument("--samples", type=int, default=5, help="snapshot reads to take")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between samples")
    p.add_argument("--timeout", type=float, default=5.0, help="per-request timeout (s)")
    p.add_argument("--center", type=float, default=1.0,
                   help="sample only the central fraction of the frame (e.g. 0.5)")
    p.add_argument("--save", help="save the first captured frame to this path")
    args = p.parse_args(argv)

    if args.stream:
        cmd_stream(args)
    elif args.url:
        cmd_snapshot(args)
    else:
        p.error("provide --url (snapshot) or --stream (MJPEG)")


if __name__ == "__main__":
    main()
