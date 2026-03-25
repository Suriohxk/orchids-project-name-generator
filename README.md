# GNN-Based Live Malware & Botnet Detection

Real-time botnet and malware detection using Graph Neural Networks (GraphSAGE/GAT) on live network traffic.

```
Network Traffic → Flow Aggregation → Graph Snapshot → GNN Inference → Dashboard & Alerts
```

## Architecture

- **Backend:** Python · FastAPI · Scapy · PyTorch Geometric
- **Frontend:** React 18 · Vite · Tailwind CSS · vis-network · Recharts
- **Models:** GraphSAGE (fast) and GAT (expressive), both with 14-dim node features

## Quick Start

### 1. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
# PyTorch Geometric requires matching torch version; see https://pyg.org/install
pip install torch-scatter torch-sparse torch-cluster -f https://data.pyg.org/whl/torch-<VERSION>+cpu.html
```

### 2. Train the model (optional — server starts in heuristic mode without a checkpoint)

```bash
python scripts/train_model.py --epochs 150 --arch sage
# Saves to data/models/best_model.pt
```

### 3. Start the backend

```bash
cd /path/to/project
MODEL_PATH=data/models/best_model.pt python -m backend.api.server
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

## Configuration

Copy `.env.example` to `.env` and edit:

```
MODEL_PATH=data/models/best_model.pt
ALERT_THRESHOLD=0.55        # score ≥ this triggers an alert
WINDOW_SECONDS=10           # sliding window size
SNAPSHOT_INTERVAL=5         # graph snapshot frequency (seconds)
CAPTURE_INTERFACE=          # leave blank for simulation mode; e.g. eth0 for live capture
```

> **Note:** Live packet capture requires root/admin privileges and a compatible pcap library.

## Project Structure

```
├── backend/
│   ├── capture/        packet_capture.py — Scapy capture + flow aggregation
│   ├── graph/          graph_builder.py  — flow → PyG graph conversion
│   ├── model/          gnn_model.py, trainer.py
│   ├── inference/      detector.py       — sliding-window pipeline + alerts
│   └── api/            server.py         — FastAPI REST + WebSocket
├── frontend/
│   └── src/            React dashboard
├── scripts/
│   ├── train_model.py
│   └── evaluate_model.py
├── notebooks/
│   └── GNN_Botnet_Training.py   — training + visualization notebook
├── data/
│   ├── models/         saved checkpoints
│   └── processed/      plots, datasets
└── docs/
    └── PROJECT_REPORT.md
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | System health and metrics |
| `/api/snapshot` | GET | Latest graph snapshot with scores |
| `/api/alerts` | GET | Recent alerts (`?n=50`) |
| `/api/history` | GET | Last N snapshot summaries |
| `/api/config` | POST | Update alert threshold |
| `/ws/live` | WebSocket | Real-time snapshot stream |

## Detection Signals

| Signal | Description |
|--------|-------------|
| High unique destinations | Port scanning / reconnaissance |
| High SYN-without-ACK ratio | TCP SYN scan |
| High unique sources | Fan-in (C&C node) |
| Dense bot subgraph | Coordinated botnet cluster |
| GNN anomaly score | Graph-structural anomaly |

## Evaluation (Synthetic Dataset)

| Metric | GraphSAGE |
|--------|-----------|
| Precision | ~0.91 |
| Recall | ~0.88 |
| F1 | ~0.89 |
| ROC-AUC | ~0.97 |
| Inference latency | ~2 ms/snapshot |

See [docs/PROJECT_REPORT.md](docs/PROJECT_REPORT.md) for full details.

---

*Proof-of-concept. Not for production use as a security control.*
