"""
GNN model definitions for botnet/malware node classification.

Two architectures available:
  • BotnetGraphSAGE  – GraphSAGE with skip connections (fast, production-friendly)
  • BotnetGAT        – Graph Attention Network (more expressive, slightly slower)

Both output per-node anomaly scores in [0, 1].
"""

from __future__ import annotations
from typing import Optional

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.nn import SAGEConv, GATConv, global_mean_pool, BatchNorm
    from torch_geometric.data import Data
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


if TORCH_AVAILABLE:

    class BotnetGraphSAGE(nn.Module):
        """
        3-layer GraphSAGE with residual connections for node-level anomaly scoring.
        Input:  node features (N × F_n),  edge_index (2 × E)
        Output: per-node score in [0,1]   (N,)
        """

        def __init__(
            self,
            in_channels: int = 14,
            hidden_channels: int = 64,
            num_layers: int = 3,
            dropout: float = 0.3,
        ):
            super().__init__()
            self.convs = nn.ModuleList()
            self.bns = nn.ModuleList()
            self.dropout = dropout

            # Layer dimensions
            dims = [in_channels] + [hidden_channels] * num_layers

            for i in range(num_layers):
                self.convs.append(SAGEConv(dims[i], dims[i + 1]))
                self.bns.append(BatchNorm(dims[i + 1]))

            # Input projection for residual (only if shapes differ)
            self.proj = nn.Linear(in_channels, hidden_channels) if in_channels != hidden_channels else None

            # Classification head
            self.head = nn.Sequential(
                nn.Linear(hidden_channels, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

        def forward(self, x: "torch.Tensor", edge_index: "torch.Tensor", **kwargs) -> "torch.Tensor":
            residual = self.proj(x) if self.proj is not None else x

            for i, (conv, bn) in enumerate(zip(self.convs, self.bns)):
                h = conv(x, edge_index)
                h = bn(h)
                h = F.relu(h)
                h = F.dropout(h, p=self.dropout, training=self.training)
                # Residual after first layer
                if i == 0:
                    x = h + residual
                else:
                    x = h + x
            return self.head(x).squeeze(-1)

        def predict(self, data: "Data") -> "torch.Tensor":
            self.eval()
            with torch.no_grad():
                return self.forward(data.x, data.edge_index)


    class BotnetGAT(nn.Module):
        """
        3-layer Graph Attention Network for node-level anomaly scoring.
        Uses multi-head attention and edge features (projected to node space).
        """

        def __init__(
            self,
            in_channels: int = 14,
            hidden_channels: int = 64,
            heads: int = 4,
            dropout: float = 0.3,
        ):
            super().__init__()
            self.dropout = dropout

            self.conv1 = GATConv(in_channels, hidden_channels // heads, heads=heads, dropout=dropout, concat=True)
            self.bn1 = BatchNorm(hidden_channels)

            self.conv2 = GATConv(hidden_channels, hidden_channels // heads, heads=heads, dropout=dropout, concat=True)
            self.bn2 = BatchNorm(hidden_channels)

            self.conv3 = GATConv(hidden_channels, hidden_channels, heads=1, dropout=dropout, concat=False)
            self.bn3 = BatchNorm(hidden_channels)

            self.head = nn.Sequential(
                nn.Linear(hidden_channels, 32),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

        def forward(self, x: "torch.Tensor", edge_index: "torch.Tensor", **kwargs) -> "torch.Tensor":
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = F.elu(self.bn1(self.conv1(x, edge_index)))
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = F.elu(self.bn2(self.conv2(x, edge_index)))
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = F.elu(self.bn3(self.conv3(x, edge_index)))
            return self.head(x).squeeze(-1)

        def predict(self, data: "Data") -> "torch.Tensor":
            self.eval()
            with torch.no_grad():
                return self.forward(data.x, data.edge_index)


    def build_model(arch: str = "sage", **kwargs) -> nn.Module:
        """Factory function."""
        if arch.lower() == "sage":
            return BotnetGraphSAGE(**kwargs)
        elif arch.lower() == "gat":
            return BotnetGAT(**kwargs)
        else:
            raise ValueError(f"Unknown architecture: {arch}")


else:
    # Stub when PyTorch is not installed (frontend/demo only)
    class BotnetGraphSAGE:  # type: ignore
        pass

    class BotnetGAT:  # type: ignore
        pass

    def build_model(arch="sage", **kwargs):  # type: ignore
        raise RuntimeError("PyTorch not available")
