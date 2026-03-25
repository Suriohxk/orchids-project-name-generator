#!/usr/bin/env python3
"""
Evaluation script.
Loads a saved model checkpoint and evaluates it on fresh synthetic data
or a labeled PCAP-derived graph dataset.
"""
import argparse
import logging
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.model.trainer import Trainer, generate_dataset

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='data/models/best_model.pt')
    parser.add_argument('--arch', choices=['sage', 'gat'], default='sage')
    parser.add_argument('--n-graphs', type=int, default=100)
    parser.add_argument('--n-nodes', type=int, default=50)
    parser.add_argument('--bot-nodes', type=int, default=8)
    args = parser.parse_args()

    logging.info('Generating evaluation dataset…')
    dataset = generate_dataset(n_graphs=args.n_graphs, n_nodes=args.n_nodes, n_bot_nodes=args.bot_nodes)

    trainer = Trainer(arch=args.arch)
    trainer.load_checkpoint(os.path.basename(args.model))

    metrics = trainer.evaluate(dataset)

    print('\n' + '='*50)
    print('Evaluation Results')
    print('='*50)
    for k, v in metrics.items():
        val_str = f'{v:.4f}' if isinstance(v, float) else str(v)
        print(f'  {k:30s}: {val_str}')
    print('='*50 + '\n')

    return metrics


if __name__ == '__main__':
    main()
