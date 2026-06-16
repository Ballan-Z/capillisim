"""Portable core: geometry, palette, planner, matcher, plan/state.

Pure Python, no camera/projector/file-dialog dependencies, so this layer can be
reused unchanged when the project moves to a phone-only build (Milestone 5).

Planned modules (see docs/ARCHITECTURE.md, implemented from Milestone 1):
- geometry  hex cap packing, grid layout, table-mm <-> cell-index conversions
- palette   sRGB<->Lab, CIEDE2000 distance, binning to achievable cap colors
- planner   image -> GridPlan (+ bill of materials), in either size direction
- matcher   cap color + state -> best empty cell, or reject ("set aside")
- plan      GridPlan + filled/empty state, JSON project file for staged builds
"""
