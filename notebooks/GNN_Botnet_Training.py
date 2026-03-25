# %% [markdown]
# # GNN-Based Botnet Detection — Training Notebook
#
# This notebook demonstrates the full pipeline:
# 1. Dataset generation (synthetic graphs simulating botnet topology)
# 2. GNN model training (GraphSAGE and GAT)
# 3. Evaluation: Precision, Recall, F1, ROC-AUC
# 4. Feature importance analysis
# 5. Graph visualization of detection results

# %%
import sys
sys.path.insert(0, '..')

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import json
import os

# %%
# =============================================================================
# 1. DATASET GENERATION
# =============================================================================
from backend.model.trainer import generate_dataset, generate_synthetic_graph

# Generate 300 graphs: 50 nodes each, 8 botnet nodes
dataset = generate_dataset(n_graphs=300, n_nodes=50, n_bot_nodes=8)
split = int(len(dataset) * 0.8)
train_data = dataset[:split]
val_data = dataset[split:]

print(f"Total graphs: {len(dataset)}")
print(f"  Train: {len(train_data)}, Val: {len(val_data)}")
print(f"  Nodes per graph: {dataset[0].num_nodes}")
print(f"  Botnet nodes per graph: {dataset[0].y.sum().item()}")
print(f"  Node feature dim: {dataset[0].x.shape[1]}")

# %%
# Feature analysis
import torch
all_feats = torch.cat([d.x for d in dataset], dim=0).numpy()
all_labels = torch.cat([d.y for d in dataset], dim=0).numpy()

feature_names = [
    'packets (log)', 'bytes (log)', 'src_port_div', 'dst_port_div',
    'unique_dests', 'unique_srcs', 'tcp_ratio', 'udp_ratio', 'icmp_ratio',
    'syn_ratio', 'mean_pps', 'mean_bps (log)', 'is_private', 'degree'
]

# Per-feature mean for benign vs botnet
benign_means = all_feats[all_labels == 0].mean(axis=0)
botnet_means = all_feats[all_labels == 1].mean(axis=0)

fig, ax = plt.subplots(figsize=(14, 4))
x = np.arange(len(feature_names))
w = 0.35
ax.bar(x - w/2, benign_means, w, label='Benign', color='#22c55e', alpha=0.8)
ax.bar(x + w/2, botnet_means, w, label='Botnet', color='#ef4444', alpha=0.8)
ax.set_xticks(x)
ax.set_xticklabels(feature_names, rotation=45, ha='right', fontsize=9)
ax.set_title('Mean Feature Values: Benign vs Botnet Nodes')
ax.legend()
ax.set_facecolor('#0f172a')
fig.patch.set_facecolor('#0f172a')
ax.tick_params(colors='white')
ax.title.set_color('white')
ax.yaxis.label.set_color('white')
for spine in ax.spines.values():
    spine.set_edgecolor('#334155')
plt.tight_layout()
plt.savefig('../data/processed/feature_comparison.png', dpi=150, bbox_inches='tight')
plt.show()
print("Feature analysis saved.")

# %%
# =============================================================================
# 2. TRAINING
# =============================================================================
from backend.model.trainer import Trainer

print("Training GraphSAGE model…")
trainer_sage = Trainer(arch='sage', hidden_channels=64, num_layers=3, lr=1e-3, checkpoint_dir='../data/models')
history_sage = trainer_sage.train(train_data, val_data, epochs=100, patience=15)
metrics_sage = trainer_sage.evaluate(val_data)
print("GraphSAGE:", metrics_sage)

# %%
# Training curves
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

axes[0].plot(history_sage['train_loss'], color='#3b82f6', label='Loss')
axes[0].set_title('Training Loss', color='white')
axes[0].set_facecolor('#0f172a')
axes[0].tick_params(colors='white')
for spine in axes[0].spines.values():
    spine.set_edgecolor('#334155')

axes[1].plot(history_sage['val_f1'], color='#22c55e', label='F1')
axes[1].plot(history_sage['val_precision'], color='#3b82f6', label='Precision', linestyle='--')
axes[1].plot(history_sage['val_recall'], color='#f97316', label='Recall', linestyle=':')
axes[1].set_title('Validation Metrics', color='white')
axes[1].legend()
axes[1].set_facecolor('#0f172a')
axes[1].tick_params(colors='white')
for spine in axes[1].spines.values():
    spine.set_edgecolor('#334155')

for ax in axes:
    ax.title.set_color('white')

fig.patch.set_facecolor('#0f172a')
plt.tight_layout()
plt.savefig('../data/processed/training_curves.png', dpi=150, bbox_inches='tight')
plt.show()

# %%
# =============================================================================
# 3. EVALUATION
# =============================================================================
from sklearn.metrics import (
    precision_recall_fscore_support, roc_auc_score,
    confusion_matrix, roc_curve, precision_recall_curve
)

trainer_sage.model.eval()
all_probs, all_labels_eval = [], []
for d in val_data:
    probs = trainer_sage.model(d.x, d.edge_index).detach().numpy()
    all_probs.append(probs)
    all_labels_eval.append(d.y.numpy())

probs = np.concatenate(all_probs)
labels_eval = np.concatenate(all_labels_eval)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# ROC curve
fpr, tpr, _ = roc_curve(labels_eval, probs)
auc = roc_auc_score(labels_eval, probs)
axes[0].plot(fpr, tpr, color='#22c55e', lw=2, label=f'AUC={auc:.3f}')
axes[0].plot([0,1],[0,1], color='#475569', linestyle='--', lw=1)
axes[0].set_xlabel('FPR', color='white'); axes[0].set_ylabel('TPR', color='white')
axes[0].set_title('ROC Curve', color='white')
axes[0].legend(labelcolor='white')
axes[0].set_facecolor('#0f172a')
axes[0].tick_params(colors='white')
for s in axes[0].spines.values(): s.set_edgecolor('#334155')

# Precision-Recall curve
prec_curve, rec_curve, _ = precision_recall_curve(labels_eval, probs)
axes[1].plot(rec_curve, prec_curve, color='#3b82f6', lw=2)
axes[1].set_xlabel('Recall', color='white'); axes[1].set_ylabel('Precision', color='white')
axes[1].set_title('Precision-Recall Curve', color='white')
axes[1].set_facecolor('#0f172a')
axes[1].tick_params(colors='white')
for s in axes[1].spines.values(): s.set_edgecolor('#334155')

fig.patch.set_facecolor('#0f172a')
plt.tight_layout()
plt.savefig('../data/processed/evaluation_curves.png', dpi=150, bbox_inches='tight')
plt.show()

print("\n=== Final Metrics ===")
for k, v in metrics_sage.items():
    print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

# %%
# =============================================================================
# 4. GRAPH VISUALIZATION — detection on a sample graph
# =============================================================================
import networkx as nx

sample = val_data[0]
trainer_sage.model.eval()
scores = trainer_sage.model(sample.x, sample.edge_index).detach().numpy()
labels_sample = sample.y.numpy()

G = nx.DiGraph()
for i in range(sample.num_nodes):
    G.add_node(i)
edge_list = sample.edge_index.numpy().T
for (u, v) in edge_list:
    G.add_edge(int(u), int(v))

pos = nx.spring_layout(G, seed=42, k=1.2)
node_colors = ['#ef4444' if labels_sample[i] == 1 else '#22c55e' for i in range(sample.num_nodes)]
node_sizes = [200 + scores[i] * 400 for i in range(sample.num_nodes)]

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.patch.set_facecolor('#0f172a')

for ax, (title, colors) in zip(axes, [
    ("Ground Truth Labels", ['#ef4444' if l == 1 else '#22c55e' for l in labels_sample]),
    ("GNN Predicted Scores", [plt.cm.RdYlGn_r(s) for s in scores])
]):
    ax.set_facecolor('#0f172a')
    nx.draw_networkx(G, pos=pos, ax=ax, node_color=colors, node_size=node_sizes,
                     with_labels=False, edge_color='#334155', arrows=True,
                     arrowsize=10, width=0.5)
    ax.set_title(title, color='white')
    ax.axis('off')

# Legend
patches = [
    mpatches.Patch(color='#ef4444', label='Botnet'),
    mpatches.Patch(color='#22c55e', label='Benign'),
]
axes[0].legend(handles=patches, loc='lower right', labelcolor='white',
               facecolor='#1e293b', edgecolor='#334155')

plt.tight_layout()
plt.savefig('../data/processed/graph_detection.png', dpi=150, bbox_inches='tight')
plt.show()
print("All notebook outputs saved to data/processed/")
