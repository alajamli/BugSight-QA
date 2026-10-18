"""CLI entry point for training the floating-object detector."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.model.evaluate import evaluate_model  # noqa: E402
from src.model.trainer import _find_best_weights, load_config  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train the BugSight detector.")
    p.add_argument("--config", type=Path, default=Path("configs/train.yaml"))
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--batch", type=int, default=None)
    p.add_argument("--device", type=str, default=None)
    p.add_argument("--evaluate-only", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    if args.epochs is not None:
        cfg.epochs = args.epochs
    if args.batch is not None:
        cfg.batch = args.batch
    if args.device is not None:
        cfg.device = args.device

    if not args.evaluate_only:
        print(f"[train] Starting: {cfg.weights} | {cfg.epochs} epochs | device={cfg.device}")
        from ultralytics import YOLO

        model = YOLO(cfg.weights)
        model.train(**cfg.to_train_kwargs())
        weights_path = _find_best_weights(cfg)
        print(f"[train] Best weights: {weights_path}")
    else:
        weights_path = _find_best_weights(cfg)

    print("[train] Running evaluation on test split...")
    metrics = evaluate_model(weights_path, cfg.data_yaml, device=cfg.device)
    print(json.dumps(metrics.to_dict(), indent=2))


if __name__ == "__main__":
    main()
