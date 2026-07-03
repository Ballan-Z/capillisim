# Connecting the Phone to the PC (first hardware step)

Goal: confirm the PC can see the phone's camera and read cap colors over your
Wi-Fi, before any projector work. No projector and no OpenCV needed for this:
just Python + Pillow (already installed) and an IP-webcam app on the phone.

## How the link works

Phone and PC are on the **same Wi-Fi network**. An app on the phone runs a tiny
web server that serves its camera over HTTP. The PC reads from the phone's local
IP address. Two endpoints matter:

- **Snapshot** (a single JPEG): `http://<phone-ip>:<port>/shot.jpg` (simplest;
  this is what we use first).
- **Video** (continuous MJPEG): `http://<phone-ip>:<port>/video`, for the live
  loop later (read with OpenCV).

## 1. Install an IP-webcam app

- **Android:** "IP Webcam" (Pavel Khlebovich) is the easiest; it serves both
  `/shot.jpg` and `/video`. Free.
- **iOS:** use any app that advertises an "IP camera" / "MJPEG" / "HTTP server"
  mode (e.g. "IP Camera Lite"). Note the snapshot/stream URLs it shows. (Apps
  like DroidCam/EpocCam instead present the phone as a virtual webcam; those are
  read by OpenCV as a normal camera index rather than a URL.)

## 2. Start the server and get the URL

1. Put the phone and PC on the **same** Wi-Fi (not a guest/isolated network).
2. Open the app and tap "Start server".
3. It shows a URL like `http://192.168.1.42:8080`. Your snapshot URL is that plus
   the app's still-image path, commonly `/shot.jpg`.
4. **Sanity check from the PC first:** open `http://192.168.1.42:8080/shot.jpg`
   in the PC's browser. If you see a photo from the phone, the link is good.

## 3. Read caps from the PC

From the project root:

```bash
python -m cap_mosaic.app.camera_check --url http://192.168.1.42:8080/shot.jpg
```

Hold a cap in front of the phone. Each sample prints what it sees, e.g.:

```
  [1/5] 1920x1080  rgb=(38, 79, 162)    reads as: blue   (dE=1.4)
```

Useful flags:
- `--save seen.png`: save the first frame to eyeball framing and lighting.
- `--center 0.5`: sample only the middle of the frame (hold the cap centered).
- `--samples 20 --interval 0.5`: read more often while you test colors.

## 4. (Later) Live video stream

Once snapshots work, the continuous stream (needs `pip install opencv-python`):

```bash
python -m cap_mosaic.app.camera_check --stream http://192.168.1.42:8080/video --show
```

## Troubleshooting

- **Can't connect / timeout:** phone and PC on the same network? Confirm the
  phone's IP in the app. Try the URL in the PC browser. A PC firewall can block
  outbound LAN requests.
- **Colors look off:** even, diffuse lighting helps; avoid glare on metallic
  caps; use `--center 0.5` so the background isn't sampled.
- **iOS sleeps / stops streaming:** keep the app in the foreground and disable
  auto-lock while building.
- **Wrong port/path:** endpoints vary by app; check the app's on-screen help for
  its exact snapshot and video URLs.
