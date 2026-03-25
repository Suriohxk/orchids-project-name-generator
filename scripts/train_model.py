#!/usr/bin/env python3
"""
Standalone training script.
Usage:
  python scripts/train_model.py [--arch sage|gat] [--epochs 150]
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.model.trainer import train_default, Trainer, generate_dataset
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)


def main():
    parser = argparse.ArgumentParser(description='Train GNN botnet detection model')
    parser.add_argument('--arch', choices=['sage', 'gat'], default='sage')
    parser.add_argument('--epochs', type=int, default=150)
    parser.add_argument('--hidden', type=int, default=64)
    parser.add_argument('--layers', type=int, default=3)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--n-graphs', type=int, default=300)
    parser.add_argument('--n-nodes', type=int, default=50)
    parser.add_argument('--bot-nodes', type=int, default=8)
    parser.add_argument('--patience', type=int, default=20)
    parser.add_argument('--output-dir', default='data/models')
    args = parser.parse_args()

    logging.info(f'Generating dataset: {args.n_graphs} graphs, {args.n_nodes} nodes each, {args.bot_nodes} bot nodes…')
    dataset = generate_dataset(n_graphs=args.n_graphs, n_nodes=args.n_nodes, n_bot_nodes=args.bot_nodes)
    split = int(len(dataset) * 0.8)
    train_graphs = dataset[:split]
    val_graphs = dataset[split:]

    logging.info(f'Architecture: {args.arch.upper()}, hidden={args.hidden}, layers={args.layers}')
    trainer = Trainer(
        arch=args.arch,
        hidden_channels=args.hidden,
        num_layers=args.layers,
        lr=args.lr,
        checkpoint_dir=args.output_dir,
    )

    history = trainer.train(train_graphs, val_graphs, epochs=args.epochs, patience=args.patience)
    final = trainer.evaluate(val_graphs)

    logging.info('\n' + '='*50)
    logging.info('Final Validation Metrics')
    logging.info('='*50)
    for k, v in final.items():
        logging.info(f'  {k:30s}: {v:.4f}' if isinstance(v, float) else f'  {k:30s}: {v}')

    hist_path = os.path.join(args.output_dir, 'training_history.json')
    with open(hist_path, 'w') as f:
        json.dump({'history': history, 'final': final, 'config': vars(args)}, f, indent=2)
    logging.info(f'\nTraining history saved to {hist_path}')
    logging.info(f'Model checkpoint: {args.output_dir}/best_model.pt')


if __name__ == '__main__':
    main()
