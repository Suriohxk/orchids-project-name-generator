"""
FastAPI backend server.

Endpoints:
  GET  /api/status          – system health + metrics
  GET  /api/snapshot        – latest graph snapshot with scores
  GET  /api/alerts          – recent alerts list
  GET  /api/history         – last N snapshot summaries
  POST /api/config          – update alert threshold, etc.
  WS   /ws/live             – WebSocket stream of real-time results
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Make sure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.inference.detector import BotnetDetector, DetectionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Globals / state
# ---------------------------------------------------------------------------

detector: Optional[BotnetDetector] = None
ws_clients: List[WebSocket] = []
latest_result_json: Optional[str] = None


def on_detection_result(result: DetectionResult):
    """Called by detector on every new snapshot; broadcast to WS clients."""
    global latest_result_json
    data = result.to_dict()
    latest_result_json = json.dumps(data)
    asyncio.run_coroutine_threadsafe(broadcast(latest_result_json), loop)


async def broadcast(message: str):
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)


loop: asyncio.AbstractEventLoop = None  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector, loop
    loop = asyncio.get_event_loop()

    model_path = os.environ.get("MODEL_PATH", "data/models/best_model.pt")
    interface = os.environ.get("CAPTURE_INTERFACE", None)

    detector = BotnetDetector(
        model_path=model_path,
        alert_threshold=float(os.environ.get("ALERT_THRESHOLD", "0.55")),
        window_seconds=float(os.environ.get("WINDOW_SECONDS", "10")),
        snapshot_interval=float(os.environ.get("SNAPSHOT_INTERVAL", "5")),
        interface=interface,
        on_result=on_detection_result,
    )
    detector.start()
    logger.info("BotnetDetector started.")
    yield
    detector.stop()
    logger.info("BotnetDetector stopped.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GNN Botnet Detector",
    description="Real-time graph neural network based botnet/malware detection",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_status():
    if detector is None:
        return {"status": "starting"}
    return {
        "status": "running",
        "timestamp": time.time(),
        "metrics": detector.get_metrics(),
        "alert_threshold": detector.alert_threshold,
    }


@app.get("/api/snapshot")
async def get_snapshot():
    if detector is None:
        raise HTTPException(503, "Detector not ready")
    snap = detector.get_latest_snapshot()
    if snap is None:
        return {"message": "No snapshot available yet", "nodes": [], "edges": [], "alerts": []}
    return snap


@app.get("/api/alerts")
async def get_alerts(n: int = 50):
    if detector is None:
        raise HTTPException(503, "Detector not ready")
    return {"alerts": detector.get_recent_alerts(n)}


@app.get("/api/history")
async def get_history(n: int = 20):
    if detector is None:
        raise HTTPException(503, "Detector not ready")
    return {"snapshots": detector.get_recent_results(n)}


class ConfigUpdate(BaseModel):
    alert_threshold: Optional[float] = None
    window_seconds: Optional[float] = None


@app.post("/api/config")
async def update_config(cfg: ConfigUpdate):
    if detector is None:
        raise HTTPException(503, "Detector not ready")
    if cfg.alert_threshold is not None:
        detector.alert_threshold = max(0.0, min(1.0, cfg.alert_threshold))
    return {"status": "ok", "alert_threshold": detector.alert_threshold}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(ws_clients)}")
    try:
        # Send current snapshot immediately
        if latest_result_json:
            await websocket.send_text(latest_result_json)
        while True:
            # Keep-alive ping
            await asyncio.sleep(1)
            try:
                await websocket.send_text('{"type":"ping"}')
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in ws_clients:
            ws_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(ws_clients)}")


# ---------------------------------------------------------------------------
# Serve built frontend (production)
# ---------------------------------------------------------------------------

frontend_dist = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("backend.api.server:app", host="0.0.0.0", port=8000, reload=False)
