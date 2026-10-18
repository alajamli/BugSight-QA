"""Per-class evaluation report (no heavy imports, easy to unit-test).

The global mAP hides which bug types the model actually misses: an earlier
model scored mAP50 = 0.70 while detecting only 23% of screen_tear and 10% of
uv_stretch boxes. This module turns Ultralytics validation arrays into a table
with recall, precision, how often each class is missed or confused, and short
hints about what to fix.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml

WEAK_RECALL = 0.6
WEAK_PRECISION = 0.6
CONFUSION_ALERT = 0.2


def count_instances(data_yaml: str | Path, split: str = "test") -> dict[int, int]:
    """Count labelled boxes per class id in one split of a YOLO dataset."""
    data_yaml = Path(data_yaml)
    cfg = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    root = Path(cfg["path"]) if cfg.get("path") else data_yaml.parent
    if not root.is_absolute() and cfg.get("path"):
        root = data_yaml.parent / root
    images_dir = root / cfg[split]
    # Ultralytics maps .../images/<split> to .../labels/<split> (last "images" part).
    parts = list(images_dir.parts)
    if "images" in parts:
        parts[len(parts) - 1 - parts[::-1].index("images")] = "labels"
    labels_dir = Path(*parts)
    counts: dict[int, int] = {}
    for label_file in labels_dir.glob("*.txt"):
        for line in label_file.read_text().splitlines():
            parts = line.split()
            if parts:
                counts[int(parts[0])] = counts.get(int(parts[0]), 0) + 1
    return counts


def build_class_report(
    names: Sequence[str],
    ap_class_index: Sequence[int],
    precision: Sequence[float],
    recall: Sequence[float],
    ap50: Sequence[float],
    ap50_95: Sequence[float],
    instances: Mapping[int, int],
    matrix: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    """One row per class.

    ``matrix`` is the Ultralytics confusion matrix, shape (nc+1, nc+1), indexed
    ``[predicted, true]`` with the last row/column meaning "background".
    """
    position = {int(c): i for i, c in enumerate(ap_class_index)}
    n = len(names)
    rows: list[dict[str, Any]] = []
    for class_id, name in enumerate(names):
        i = position.get(class_id)
        row: dict[str, Any] = {
            "class": name,
            "instances": int(instances.get(class_id, 0)),
            "precision": float(precision[i]) if i is not None else 0.0,
            "recall": float(recall[i]) if i is not None else 0.0,
            "ap50": float(ap50[i]) if i is not None else 0.0,
            "ap50_95": float(ap50_95[i]) if i is not None else 0.0,
        }
        if matrix is not None and matrix.shape[0] > n:
            true_col = matrix[:, class_id]
            total = float(true_col.sum())
            row["missed_rate"] = float(true_col[n] / total) if total else 0.0
            others = true_col[:n].astype(float).copy()
            others[class_id] = 0.0
            if total and others.max() > 0:
                row["main_confusion"] = names[int(others.argmax())]
                row["main_confusion_rate"] = float(others.max() / total)
            else:
                row["main_confusion"] = None
                row["main_confusion_rate"] = 0.0
            predicted_row = matrix[class_id, :].astype(float)
            row["false_positives"] = int(predicted_row.sum() - predicted_row[class_id])
        rows.append(row)
    return rows


def advice(row: Mapping[str, Any]) -> list[str]:
    """Plain-language hints for one class row."""
    hints = []
    if row["instances"] and row["recall"] < WEAK_RECALL:
        if row.get("missed_rate", 0) >= 0.5:
            hints.append(
                "mostly MISSED (seen as background): check the defect is really visible "
                "in the labelled box, then add more examples"
            )
        else:
            hints.append("low recall: add more varied examples")
    # With a confusion matrix, only talk about false alarms if there were any
    # (an untrained model predicts nothing: precision 0 but no false alarms).
    has_false_alarms = row.get("false_positives", 1) > 0
    if row["precision"] < WEAK_PRECISION and row["instances"] and has_false_alarms:
        hints.append("many false alarms: add hard negatives (look-alike clean regions)")
    if row.get("main_confusion") and row.get("main_confusion_rate", 0) >= CONFUSION_ALERT:
        hints.append(f"often confused with {row['main_confusion']}")
    return hints


def format_report(
    rows: Sequence[Mapping[str, Any]],
    overall: Mapping[str, float],
    *,
    split: str = "test",
    weights: str | Path | None = None,
) -> str:
    """Markdown report: overall metrics, per-class table, weak-class hints."""
    lines = [f"# Per-class evaluation ({split} split)", ""]
    if weights:
        lines += [f"Weights: `{weights}`", ""]
    lines += [
        f"Overall: precision {overall['precision']:.3f} | recall {overall['recall']:.3f} | "
        f"mAP50 {overall['mAP50']:.3f} | mAP50-95 {overall['mAP50_95']:.3f}",
        "",
    ]
    has_confusion = any("missed_rate" in r for r in rows)
    header = "| Class | Boxes | Precision | Recall | AP50 | AP50-95 |"
    divider = "|---|---:|---:|---:|---:|---:|"
    if has_confusion:
        header += " Missed | False alarms | Mostly confused with |"
        divider += "---:|---:|---|"
    lines += [header, divider]
    for r in rows:
        line = (
            f"| {r['class']} | {r['instances']} | {r['precision']:.2f} | {r['recall']:.2f} "
            f"| {r['ap50']:.2f} | {r['ap50_95']:.2f} |"
        )
        if has_confusion:
            confused = r.get("main_confusion")
            confused_text = f"{confused} ({r['main_confusion_rate']:.0%})" if confused else "-"
            line += f" {r.get('missed_rate', 0):.0%} | {r.get('false_positives', 0)} | {confused_text} |"
        lines.append(line)

    weak = [(r["class"], advice(r)) for r in rows if advice(r)]
    lines += ["", "## Where to improve", ""]
    if weak:
        for name, hints in weak:
            lines.append(f"- **{name}**: " + "; ".join(hints))
    else:
        lines.append("- No weak class: every class has recall and precision above 0.6.")
    return "\n".join(lines) + "\n"


def save_report(
    rows: Sequence[Mapping[str, Any]],
    overall: Mapping[str, float],
    out_dir: str | Path,
    tag: str,
    *,
    split: str = "test",
    weights: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write ``<tag>_<split>.md`` and ``.json`` and return their paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    markdown = out / f"{tag}_{split}.md"
    data = out / f"{tag}_{split}.json"
    markdown.write_text(
        format_report(rows, overall, split=split, weights=weights), encoding="utf-8"
    )
    data.write_text(
        json.dumps(
            {
                "split": split,
                "weights": str(weights) if weights else None,
                "overall": dict(overall),
                "classes": list(rows),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return markdown, data
