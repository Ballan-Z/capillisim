"""PC shell: see the cap.

Planned modules (see docs/ARCHITECTURE.md):
- cap_reader  detect the cap circle and read its dominant color robustly,
              masking specular glare from metallic caps. Read the cap outside
              the projector beam so projection light doesn't tint the color.
- brand       DEFERRED. Logo/brand classifier, layered on top of color as an
              optional signal. Stubbed to return None until Milestone 4.
"""
