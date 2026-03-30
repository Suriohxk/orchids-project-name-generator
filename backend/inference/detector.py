"""
Sliding-window inference engine.

Wires together:
  PacketCapture → GraphBuilder → GNN → alerts + metrics
"""

from __future__ import annotations

import os
import time
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from backend.capture.packet_capture import FlowRecord, PacketCapture
from backend.graph.graph_builder import GraphBuilder, GraphSnapshot
from backend.model.gnn_model import build_model


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    timestamp: float
    node_ip: str
    score: float
    reason: str
    snapshot_id: int

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "node_ip": self.node_ip,
            "score": round(self.score, 4),
            "reason": self.reason,
            "snapshot_id": self.snapshot_id,
        }


@dataclass
class DetectionResult:
    snapshot: GraphSnapshot
    alerts: List[Alert]
    latency_ms: float
    snapshot_id: int

    def to_dict(self) -> dict:
        d = self.snapshot.to_dict()
        d["alerts"] = [a.to_dict() for a in self.alerts]
        d["latency_ms"] = round(self.latency_ms, 2)
        d["snapshot_id"] = self.snapshot_id
        return d


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class BotnetDetector:
    """
    Orchestrates capture → graph → GNN → alert pipeline.
    Runs inference in a background thread; results are pushed to subscribers
    via callbacks.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        arch: str = "sage",
        alert_threshold: float = 0.55,
        window_seconds: float = 10.0,
        snapshot_interval: float = 5.0,
        interface: Optional[str] = None,
        on_result: Optional[Callable[[DetectionResult], None]] = None,
    ):
        self.alert_threshold = alert_threshold
        self.window_seconds = window_seconds
        self.on_result = on_result
        self._snapshot_id = 0
        self._recent_results: deque = deque(maxlen=200)
        self._recent_alerts: deque = deque(maxlen=500)
        self._lock = threading.Lock()
        self._metrics = {
            "total_snapshots": 0,
            "total_alerts": 0,
            "avg_latency_ms": 0.0,
            "last_snapshot_time": 0.0,
        }

        # Build graph builder
        self._builder = GraphBuilder()

        # Load or build model
        self._model = None
        if TORCH_AVAILABLE:
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            try:
                self._model = build_model(arch=arch, in_channels=14, hidden_channels=64, num_layers=3).to(self._device)
                if model_path and os.path.exists(model_path):
                    self._model.load_state_dict(torch.load(model_path, map_location=self._device, weights_only=True))
                    logger.info(f"Loaded model from {model_path}")
                else:
                    logger.warning("No model checkpoint found – using random weights (for demo). Run training first.")
                self._model.eval()
            except Exception as e:
                logger.warning(f"GNN model unavailable ({e}) – using heuristic scoring only.")
                self._model = None
        else:
            logger.warning("PyTorch not available – using heuristic scoring.")

        # Capture subsystem
        self._capture = PacketCapture(
            interface=interface,
            window_seconds=window_seconds,
            on_snapshot=self._process_snapshot,
            snapshot_interval=snapshot_interval,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        logger.info("Starting BotnetDetector…")
        self._capture.start()

    def stop(self):
        logger.info("Stopping BotnetDetector…")
        self._capture.stop()

    def get_recent_results(self, n: int = 20) -> List[dict]:
        with self._lock:
            results = list(self._recent_results)[-n:]
        return [r.to_dict() for r in results]

    def get_recent_alerts(self, n: int = 50) -> List[dict]:
        with self._lock:
            return [a.to_dict() for a in list(self._recent_alerts)[-n:]]

    def get_metrics(self) -> dict:
        with self._lock:
            return dict(self._metrics)

    def get_latest_snapshot(self) -> Optional[dict]:
        with self._lock:
            if self._recent_results:
                return self._recent_results[-1].to_dict()
        return None

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    def _process_snapshot(self, flows: List[FlowRecord]):
        t0 = time.perf_counter()

        snapshot = self._builder.build(flows)
        if snapshot is None:
            return

        # Run GNN or heuristic scoring
        scores = self._score_snapshot(snapshot)
        snapshot.node_predictions = scores

        # Generate alerts
        alerts = self._generate_alerts(snapshot)

        latency_ms = (time.perf_counter() - t0) * 1000

        with self._lock:
            self._snapshot_id += 1
            sid = self._snapshot_id
            result = DetectionResult(
                snapshot=snapshot,
                alerts=alerts,
                latency_ms=latency_ms,
                snapshot_id=sid,
            )
            self._recent_results.append(result)
            self._recent_alerts.extend(alerts)

            # Update metrics
            m = self._metrics
            m["total_snapshots"] += 1
            m["total_alerts"] += len(alerts)
            m["last_snapshot_time"] = time.time()
            prev_avg = m["avg_latency_ms"]
            n = m["total_snapshots"]
            m["avg_latency_ms"] = prev_avg + (latency_ms - prev_avg) / n

        if self.on_result:
            try:
                self.on_result(result)
            except Exception as e:
                logger.error(f"on_result callback error: {e}")

    def _score_snapshot(self, snapshot: GraphSnapshot) -> np.ndarray:
        """
        Return per-node anomaly scores in [0, 1].
        Blends GNN output with a heuristic signal so the dashboard
        shows meaningful scores even when the training distribution
        differs from live-simulation features.
        """
        feats = snapshot.node_features  # (N, 14)
        heuristic = np.zeros(snapshot.num_nodes, dtype=np.float32)

        if feats.shape[0] > 0:
            # [4] unique_destinations, [9] syn_ratio, [5] unique_sources
            heuristic += 0.35 * feats[:, 4]        # scanning: many unique dests
            heuristic += 0.30 * feats[:, 9]        # SYN without ACK
            heuristic += 0.15 * feats[:, 5]        # high fan-in (C&C)
            heuristic += 0.10 * np.clip(feats[:, 2] - 0.1, 0, 1)  # port diversity
            heuristic += 0.10 * np.clip(feats[:, 3] - 0.1, 0, 1)  # dst port diversity
            heuristic = np.clip(heuristic, 0, 1).astype(np.float32)

        if TORCH_AVAILABLE and self._model is not None:
            try:
                data = snapshot.to_pyg().to(self._device)
                with torch.no_grad():
                    gnn_scores = self._model(data.x, data.edge_index).cpu().numpy().astype(np.float32)
                # Blend: if GNN gives a strong signal use it; otherwise fall back to heuristic
                gnn_max = float(gnn_scores.max()) if gnn_scores.size else 0.0
                if gnn_max > 0.2:
                    return np.clip(0.5 * gnn_scores + 0.5 * heuristic, 0, 1)
                else:
                    return heuristic
            except Exception as e:
                logger.error(f"GNN inference error: {e}")

        return heuristic

    def _generate_alerts(self, snapshot: GraphSnapshot) -> List[Alert]:
        if snapshot.node_predictions is None:
            return []
        alerts = []
        for i, ip in enumerate(snapshot.node_ids):
            score = float(snapshot.node_predictions[i])
            if score >= self.alert_threshold:
                reason = self._classify_reason(snapshot.node_features[i], score)
                alerts.append(Alert(
                    timestamp=snapshot.timestamp,
                    node_ip=ip,
                    score=score,
                    reason=reason,
                    snapshot_id=self._snapshot_id,
                ))
        return alerts

    @staticmethod
    def _classify_reason(features: np.ndarray, score: float) -> str:
        reasons = []
        if features[4] > 0.4:
            reasons.append("port scan / wide destination spread")
        if features[9] > 0.3:
            reasons.append("high SYN ratio (scan or DDoS)")
        if features[5] > 0.4:
            reasons.append("high fan-in (potential C&C node)")
        if features[2] > 0.5:
            reasons.append("many source ports (evasion)")
        if not reasons:
            reasons.append("GNN anomaly score elevated")
        return "; ".join(reasons)
