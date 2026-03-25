"""
Training pipeline for the GNN botnet detector.

Supports:
  • Synthetic graph generation for quick prototyping
  • Loading pre-built graph datasets (torch_geometric InMemoryDataset format)
  • Training loop with early stopping and checkpointing
  • Evaluation: precision, recall, F1, ROC-AUC
"""

from __future__ import annotations

import os
import json
import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch_geometric.data import Data, DataLoader
    from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch/PyG not available – trainer in stub mode.")

from backend.model.gnn_model import build_model


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def generate_synthetic_graph(
    n_nodes: int = 50,
    n_bot_nodes: int = 8,
    n_features: int = 14,
    seed: int = 42,
) -> "Data":
    """
    Generate a single synthetic graph with labeled botnet nodes.
    Botnet nodes have:
      - higher unique destination counts (feature 4)
      - higher SYN ratio (feature 9)
      - low bytes (feature 1) – SYN scans are small
      - they interconnect densely among themselves
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not available")

    rng = np.random.default_rng(seed)

    x = rng.uniform(0, 0.3, size=(n_nodes, n_features)).astype(np.float32)
    labels = np.zeros(n_nodes, dtype=np.int64)

    bot_idx = rng.choice(n_nodes, size=n_bot_nodes, replace=False)
    labels[bot_idx] = 1

    # Amplify botnet features
    for b in bot_idx:
        x[b, 4] = rng.uniform(0.5, 1.0)   # unique destinations
        x[b, 9] = rng.uniform(0.4, 0.9)   # SYN ratio
        x[b, 1] = rng.uniform(0.0, 0.2)   # low bytes
        x[b, 11] = rng.uniform(0.0, 0.3)  # low bps

    # Edges: random graph + dense botnet cluster
    edges = set()
    # Random background edges
    for _ in range(n_nodes * 3):
        u, v = rng.integers(0, n_nodes, size=2)
        if u != v:
            edges.add((u, v))
    # Dense botnet edges
    for i in bot_idx:
        for j in bot_idx:
            if i != j and rng.random() < 0.7:
                edges.add((int(i), int(j)))
    # Botnet → C&C (node 0)
    for b in bot_idx:
        edges.add((int(b), 0))

    src_list = [e[0] for e in edges]
    dst_list = [e[1] for e in edges]
    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)

    return Data(
        x=torch.tensor(x, dtype=torch.float),
        edge_index=edge_index,
        y=torch.tensor(labels, dtype=torch.long),
        num_nodes=n_nodes,
    )


def generate_dataset(n_graphs: int = 200, **kwargs) -> List["Data"]:
    return [generate_synthetic_graph(seed=i, **kwargs) for i in range(n_graphs)]


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

class Trainer:
    """
    Manages the train/eval loop for node classification.
    """

    def __init__(
        self,
        arch: str = "sage",
        hidden_channels: int = 64,
        num_layers: int = 3,
        dropout: float = 0.3,
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        device: Optional[str] = None,
        checkpoint_dir: str = "data/models",
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")

        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = build_model(
            arch=arch,
            in_channels=14,
            hidden_channels=hidden_channels,
            num_layers=num_layers,
            dropout=dropout,
        ).to(self.device)

        self.optimizer = optim.Adam(self.model.parameters(), lr=lr, weight_decay=weight_decay)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, patience=10, factor=0.5)
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

    def _loss(self, pred: "torch.Tensor", labels: "torch.Tensor") -> "torch.Tensor":
        # Weighted BCE to handle class imbalance (botnet nodes ~10-20% of graph)
        pos_weight = torch.tensor([5.0], device=self.device)
        return nn.BCEWithLogitsLoss(pos_weight=pos_weight)(
            pred, labels.float()
        )

    def train_epoch(self, graphs: List["Data"]) -> float:
        self.model.train()
        total_loss = 0.0
        for data in graphs:
            data = data.to(self.device)
            self.optimizer.zero_grad()
            # Use raw logits for BCEWithLogitsLoss
            raw = self._forward_logits(data)
            loss = self._loss(raw, data.y)
            loss.backward()
            nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()
            total_loss += loss.item()
        return total_loss / max(len(graphs), 1)

    def _forward_logits(self, data: "Data") -> "torch.Tensor":
        """Forward pass returning logits (before sigmoid)."""
        # Temporarily disable sigmoid in head
        import torch.nn as _nn
        # We call forward directly on the linear layer before the sigmoid
        # Actually we patch by re-using forward and then inverting — simpler: add a logits method
        out = self.model(data.x, data.edge_index)
        # out is already [0,1] from sigmoid; convert back to logits for BCEWithLogitsLoss
        out = out.clamp(1e-6, 1 - 1e-6)
        return torch.log(out / (1 - out))

    @torch.no_grad()
    def evaluate(self, graphs: List["Data"]) -> Dict[str, float]:
        self.model.eval()
        all_probs, all_labels = [], []
        for data in graphs:
            data = data.to(self.device)
            probs = self.model(data.x, data.edge_index).cpu().numpy()
            labels = data.y.cpu().numpy()
            all_probs.append(probs)
            all_labels.append(labels)

        probs = np.concatenate(all_probs)
        labels = np.concatenate(all_labels)
        preds = (probs >= 0.5).astype(int)

        prec, rec, f1, _ = precision_recall_fscore_support(labels, preds, average="binary", zero_division=0)
        try:
            auc = float(roc_auc_score(labels, probs))
        except ValueError:
            auc = 0.0

        fp_rate = float(np.sum((preds == 1) & (labels == 0)) / max(np.sum(labels == 0), 1))
        return {
            "precision": float(prec),
            "recall": float(rec),
            "f1": float(f1),
            "roc_auc": auc,
            "false_positive_rate": fp_rate,
            "n_graphs": len(graphs),
        }

    def train(
        self,
        train_graphs: List["Data"],
        val_graphs: List["Data"],
        epochs: int = 100,
        patience: int = 15,
    ) -> Dict[str, List[float]]:
        """Full training loop with early stopping."""
        history = {"train_loss": [], "val_f1": [], "val_precision": [], "val_recall": []}
        best_f1 = 0.0
        no_improve = 0

        for epoch in range(1, epochs + 1):
            loss = self.train_epoch(train_graphs)
            metrics = self.evaluate(val_graphs)
            self.scheduler.step(1 - metrics["f1"])

            history["train_loss"].append(loss)
            history["val_f1"].append(metrics["f1"])
            history["val_precision"].append(metrics["precision"])
            history["val_recall"].append(metrics["recall"])

            if metrics["f1"] > best_f1:
                best_f1 = metrics["f1"]
                no_improve = 0
                self.save_checkpoint("best_model.pt")
                logger.info(f"Epoch {epoch:3d} | loss={loss:.4f} | F1={metrics['f1']:.3f} | AUC={metrics['roc_auc']:.3f} ✓")
            else:
                no_improve += 1
                if epoch % 10 == 0:
                    logger.info(f"Epoch {epoch:3d} | loss={loss:.4f} | F1={metrics['f1']:.3f}")

            if no_improve >= patience:
                logger.info(f"Early stopping at epoch {epoch} (no improvement for {patience} epochs)")
                break

        return history

    def save_checkpoint(self, filename: str = "model.pt"):
        path = os.path.join(self.checkpoint_dir, filename)
        torch.save(self.model.state_dict(), path)
        logger.debug(f"Checkpoint saved: {path}")

    def load_checkpoint(self, filename: str = "best_model.pt"):
        path = os.path.join(self.checkpoint_dir, filename)
        if os.path.exists(path):
            self.model.load_state_dict(torch.load(path, map_location=self.device))
            logger.info(f"Loaded checkpoint: {path}")
        else:
            logger.warning(f"No checkpoint found at {path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def train_default():
    """Train a model on synthetic data and save it."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Generating synthetic dataset…")
    dataset = generate_dataset(n_graphs=300, n_nodes=50, n_bot_nodes=8)
    split = int(len(dataset) * 0.8)
    train_graphs = dataset[:split]
    val_graphs = dataset[split:]

    logger.info(f"Training on {len(train_graphs)} graphs, validating on {len(val_graphs)}")
    trainer = Trainer(arch="sage", hidden_channels=64, num_layers=3)
    history = trainer.train(train_graphs, val_graphs, epochs=150, patience=20)

    final = trainer.evaluate(val_graphs)
    logger.info(f"\nFinal validation metrics:")
    for k, v in final.items():
        logger.info(f"  {k}: {v:.4f}")

    # Save history
    hist_path = os.path.join(trainer.checkpoint_dir, "training_history.json")
    with open(hist_path, "w") as f:
        json.dump(history, f, indent=2)
    logger.info(f"Training history saved to {hist_path}")


if __name__ == "__main__":
    train_default()
