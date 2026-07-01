"""FastAPI backend for the Mosaic Estimator."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Capillisim Mosaic Estimator")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
