"""Persistence layer: the cap dataset / inventory store.

Device-independent storage for captured caps. Kept out of ``core`` (which is
pure, no I/O) and out of the hardware shells (``vision``/``procam``/``app``).
SQLite is the backing store — single file, zero dependencies, queryable, and
available on a phone later. See ``docs/DATA_MODEL.md``.
"""

from .store import CapDataset, CapRecord, FrameRecord, import_labels_csv

__all__ = ["CapDataset", "CapRecord", "FrameRecord", "import_labels_csv"]
