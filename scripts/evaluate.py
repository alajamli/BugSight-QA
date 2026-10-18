"""Evaluate trained weights and print/save a per-class report.

Examples:
    python scripts/evaluate.py                      # newest weights, test split
    python scripts/evaluate.py --weights runs/detect/runs/bugsight_yolov8n/weights/best.pt \\
        --data data/processed/data.yaml --split val

The report is written to runs/reports/<run>_<split>.md and .json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.model.evaluate import evaluate_model  # noqa: E402
from src.model.report import format_report, save_report  # noqa: E402


def newest_weights(project: str = "runs") -> Path:
    candidates = list(Path(project).rglob("best.pt"))
    if not candidates:
        raise SystemExit(f"No best.pt found under {project}/ - train a model first.")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Per-class evaluation of a trained detector.")
    p.add_argument("--weights", type=Path, default=None, help="default: newest best.pt under runs/")
    p.add_argument("--data", type=Path, default=Path("data/processed_v2/data.yaml"))
    p.add_argument("--split", default="test", choices=["train", "val", "test"])
    p.add_argument("--device", default="cpu")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--out-dir", type=Path, default=Path("runs/reports"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    weights = args.weights or newest_weights()
    print(f"[evaluate] weights={weights} data={args.data} split={args.split}")
    metrics = evaluate_model(
        weights, args.data, device=args.device, imgsz=args.imgsz, split=args.split
    )
    print(format_report(metrics.per_class, metrics.overall(), split=args.split, weights=weights))
    run_name = weights.parent.parent.name  # .../<run>/weights/best.pt
    md, js = save_report(
        metrics.per_class,
        metrics.overall(),
        args.out_dir,
        run_name,
        split=args.split,
        weights=weights,
    )
    print(f"[evaluate] saved {md} and {js}")


if __name__ == "__main__":
    main()
