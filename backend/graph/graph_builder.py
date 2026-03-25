"""
Graph construction module.
Converts a list of FlowRecord objects into a PyTorch Geometric Data object
with meaningful node and edge features.

Node features (per IP):
  [0]  log(total_packets + 1)
  [1]  log(total_bytes + 1)
  [2]  unique_src_ports / 1000            (fan-out diversity)
  [3]  unique_dst_ports / 1000            (fan-out diversity)
  [4]  unique_destinations / 100          (scanning indicator)
  [5]  unique_sources / 100               (fan-in)
  [6]  tcp_ratio
  [7]  udp_ratio
  [8]  icmp_ratio
  [9]  syn_ratio                          (SYN without ACK → scan)
  [10] mean_pps
  [11] mean_bps_log
  [12] is_private                         (RFC-1918)
  [13] degree_centrality (approx)

Edge features (per directed IP→IP pair):
  [0]  log(packets + 1)
  [1]  log(bytes + 1)
  [2]  tcp_flag (1 if TCP)
  [3]  udp_flag
  [4]  has_syn
  [5]  mean_pps
  [6]  log(duration + 1)
"""

from __future__ import annotations

import math
import ipaddress
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

import numpy as np

try:
    import torch
    from torch_geometric.data import Data
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from backend.capture.packet_capture import FlowRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_private(ip: str) -> float:
    try:
        return float(ipaddress.ip_address(ip).is_private)
    except ValueError:
        return 0.0


def _log1p(x: float) -> float:
    return math.log1p(max(0.0, x))


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

class GraphSnapshot:
    """Lightweight graph representation (framework-agnostic)."""

    def __init__(
        self,
        node_ids: List[str],
        node_features: np.ndarray,
        edge_index: np.ndarray,       # shape (2, E)
        edge_features: np.ndarray,    # shape (E, F_e)
        edge_labels: Optional[List[Tuple[str, str]]] = None,
        timestamp: float = 0.0,
    ):
        self.node_ids = node_ids          # IP strings
        self.node_features = node_features
        self.edge_index = edge_index
        self.edge_features = edge_features
        self.edge_labels = edge_labels
        self.timestamp = timestamp
        self.node_predictions: Optional[np.ndarray] = None   # filled by inference

    @property
    def num_nodes(self) -> int:
        return len(self.node_ids)

    @property
    def num_edges(self) -> int:
        return self.edge_index.shape[1] if self.edge_index.ndim == 2 else 0

    def to_pyg(self):
        """Convert to PyTorch Geometric Data object."""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch Geometric not available")
        return Data(
            x=torch.tensor(self.node_features, dtype=torch.float),
            edge_index=torch.tensor(self.edge_index, dtype=torch.long),
            edge_attr=torch.tensor(self.edge_features, dtype=torch.float),
            num_nodes=self.num_nodes,
        )

    def to_dict(self) -> dict:
        preds = self.node_predictions.tolist() if self.node_predictions is not None else [0.0] * self.num_nodes
        return {
            "timestamp": self.timestamp,
            "nodes": [
                {
                    "id": ip,
                    "features": self.node_features[i].tolist(),
                    "score": float(preds[i]) if i < len(preds) else 0.0,
                    "is_private": bool(_is_private(ip)),
                }
                for i, ip in enumerate(self.node_ids)
            ],
            "edges": [
                {
                    "source": self.node_ids[self.edge_index[0, j]],
                    "target": self.node_ids[self.edge_index[1, j]],
                    "features": self.edge_features[j].tolist(),
                }
                for j in range(self.num_edges)
            ],
        }


class GraphBuilder:
    """
    Constructs a GraphSnapshot from a list of FlowRecords.
    """

    NODE_FEATURE_DIM = 14
    EDGE_FEATURE_DIM = 7

    def build(self, flows: List[FlowRecord], timestamp: Optional[float] = None) -> Optional[GraphSnapshot]:
        if not flows:
            return None

        import time
        ts = timestamp or time.time()

        # ------------------------------------------------------------------
        # 1. Collect per-node statistics
        # ------------------------------------------------------------------
        node_stats: Dict[str, dict] = defaultdict(lambda: {
            "packets": 0, "bytes": 0,
            "src_ports": set(), "dst_ports": set(),
            "destinations": set(), "sources": set(),
            "protocols": defaultdict(int),
            "syn_count": 0, "src_flow_count": 0, "pps_list": [], "bps_list": [],
        })

        for f in flows:
            for ip_role, ip in [("src", f.src_ip), ("dst", f.dst_ip)]:
                s = node_stats[ip]
                s["packets"] += f.packet_count
                s["bytes"] += f.byte_count
                s["protocols"][f.protocol] += f.packet_count
                s["pps_list"].append(f.pps)
                s["bps_list"].append(f.bps)
                if ip_role == "src":
                    s["src_ports"].add(f.src_port)
                    s["destinations"].add(f.dst_ip)
                    s["src_flow_count"] += 1
                    if "S" in f.flags_set and "A" not in f.flags_set:
                        s["syn_count"] += 1
                else:
                    s["dst_ports"].add(f.dst_port)
                    s["sources"].add(f.src_ip)

        node_ids = sorted(node_stats.keys())
        node_index = {ip: i for i, ip in enumerate(node_ids)}

        # ------------------------------------------------------------------
        # 2. Build node feature matrix
        # ------------------------------------------------------------------
        node_features = np.zeros((len(node_ids), self.NODE_FEATURE_DIM), dtype=np.float32)
        for i, ip in enumerate(node_ids):
            s = node_stats[ip]
            total_pkts = s["packets"] + 1e-9
            tcp = s["protocols"].get("TCP", 0)
            udp = s["protocols"].get("UDP", 0)
            icmp = s["protocols"].get("ICMP", 0)
            mean_pps = float(np.mean(s["pps_list"])) if s["pps_list"] else 0.0
            mean_bps = float(np.mean(s["bps_list"])) if s["bps_list"] else 0.0
            degree = len(s["destinations"]) + len(s["sources"])

            # SYN ratio = SYN-only flows / total outbound flows for this IP
            src_flows = max(s["src_flow_count"], 1)
            syn_ratio = min(s["syn_count"] / src_flows, 1.0)

            node_features[i] = [
                _log1p(s["packets"]),
                _log1p(s["bytes"]),
                min(len(s["src_ports"]) / 1000.0, 1.0),
                min(len(s["dst_ports"]) / 1000.0, 1.0),
                min(len(s["destinations"]) / 100.0, 1.0),
                min(len(s["sources"]) / 100.0, 1.0),
                tcp / total_pkts,
                udp / total_pkts,
                icmp / total_pkts,
                syn_ratio,
                min(mean_pps / 1000.0, 1.0),
                _log1p(mean_bps),
                _is_private(ip),
                min(degree / 50.0, 1.0),
            ]

        # ------------------------------------------------------------------
        # 3. Build edge index and features (directed: src → dst)
        # ------------------------------------------------------------------
        edge_map: Dict[Tuple[int, int], dict] = defaultdict(lambda: {
            "packets": 0, "bytes": 0,
            "tcp": 0, "udp": 0,
            "syn": 0, "pps_list": [], "durations": [],
        })

        for f in flows:
            si = node_index.get(f.src_ip)
            di = node_index.get(f.dst_ip)
            if si is None or di is None:
                continue
            key = (si, di)
            e = edge_map[key]
            e["packets"] += f.packet_count
            e["bytes"] += f.byte_count
            e["tcp"] += int(f.protocol == "TCP")
            e["udp"] += int(f.protocol == "UDP")
            e["syn"] += int("S" in f.flags_set and "A" not in f.flags_set)
            e["pps_list"].append(f.pps)
            e["durations"].append(f.duration)

        edges = list(edge_map.keys())
        if not edges:
            return None

        edge_index = np.array(edges, dtype=np.int64).T   # shape (2, E)
        edge_features = np.zeros((len(edges), self.EDGE_FEATURE_DIM), dtype=np.float32)

        for j, (si, di) in enumerate(edges):
            e = edge_map[(si, di)]
            mean_pps = float(np.mean(e["pps_list"])) if e["pps_list"] else 0.0
            mean_dur = float(np.mean(e["durations"])) if e["durations"] else 0.0
            n_flows = max(e["tcp"] + e["udp"], 1)
            edge_features[j] = [
                _log1p(e["packets"]),
                _log1p(e["bytes"]),
                float(e["tcp"] > 0),
                float(e["udp"] > 0),
                float(e["syn"] > 0),
                min(mean_pps / 1000.0, 1.0),
                _log1p(mean_dur),
            ]

        return GraphSnapshot(
            node_ids=node_ids,
            node_features=node_features,
            edge_index=edge_index,
            edge_features=edge_features,
            timestamp=ts,
        )
