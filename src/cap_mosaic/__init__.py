"""Cap Mosaic Studio: projector + camera guided bottle-cap mosaic builder.

Package layout follows the "portable core, swappable shell" principle from
docs/ARCHITECTURE.md:

- core/    pure-Python logic, no I/O (reusable on a phone later)
- vision/  PC shell: camera capture + cap recognition
- procam/  PC shell: projector output + calibration
- app/     orchestration (designer CLI, interactive build loop)
"""

__version__ = "0.0.0"
