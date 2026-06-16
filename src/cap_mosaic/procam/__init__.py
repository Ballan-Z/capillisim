"""PC shell: project the guidance.

Planned modules (see docs/ARCHITECTURE.md):
- calibrate  recover the homography between table millimetres and projector
             pixels (1:1 scale + keystone). POC: known-rectangle / 4-corner
             alignment. Enhancement: ArUco auto-calibration via the phone camera.
- render     fullscreen projector window; optional faint full template, plus a
             glowing/pulsing highlight on the single chosen cell.
"""
