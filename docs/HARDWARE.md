# Hardware

## The rig (POC)

A top-down setup on a flat table:

```
        [ projector ]        [ phone ]
             |  (straight down)  |  (streams camera over Wi-Fi)
             v                   v
   ========================================  <- flat, matte, light-neutral table
        the build area (caps placed here)
```

- **Projector**: mounted above the table pointing straight down (ceiling mount,
  a tripod with a horizontal arm, or a sturdy shelf/overhang). Top-down keeps the
  calibration geometry simple and the highlight aligned with where your hand goes.
- **Phone**: on a stand or handheld. Two jobs: (a) read the cap you hold up
  (do this just outside the projector beam so the projection doesn't tint the
  color), and (b) optionally, later, verify a cap landed in the right cell.
- **Table / board**: flat, matte, and a neutral light color so both the
  projection and the caps are clearly visible. Caps ~32 mm.
- **Lighting**: dim the room for projector contrast; add one small steady lamp
  over the cap-reading zone for stable color reads.
- **Laptop**: HDMI to the projector, Wi-Fi to the phone.

## What we already have

Per your answers: a projector, a laptop/PC, a decent smartphone, and a build
surface/frame. Good: no purchases needed to start the POC.

## Specs still needed (please fill in)

These don't block the design, but we need them to tune calibration and the max
piece size:

- **Projector:** model, native resolution (1080p preferred), brightness
  (lumens), and throw ratio + how high you can mount it. These set the largest
  table area you can cover at a usable sharpness.
- **Phone:** iOS or Android, and roughly which model (affects the camera-stream
  app choice and the future phone-only port).
- **Table/frame:** the working area dimensions (this, with cap size, bounds the
  cap count for a first piece).

## Geometry sanity checks

- **Coverage:** projected width ≈ (mounting height) / (throw ratio). Confirm the
  projector can cover your intended area from the height you can mount it.
- **Sharpness:** projected pixel pitch = projected width / horizontal resolution.
  Keep it well under the cap size (e.g. ~0.5 mm/px at 1080p over ~1 m) so the
  highlight edges are crisp.
- **Brightness:** metallic caps and ambient light fight the projection. A dim
  room and a reasonably bright projector (roughly 2500+ lumens) make the glowing
  highlight pop; we'll confirm against your actual projector.
