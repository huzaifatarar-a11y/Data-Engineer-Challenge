"""ASGI app that accepts publication POSTs and logs the JSON body."""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI

app = FastAPI(title="Publications consumer", version="0.0.1")


@app.post("/publications")
async def receive_publication(payload: dict) -> dict[str, str]:
    logging.info(json.dumps(payload))
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
