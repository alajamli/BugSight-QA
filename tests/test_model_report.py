"""Tests for the per-class report and the dataset generation script."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from src.model.report import (  # noqa: E402
    advice,
    build_class_report,
    count_instances,
    format_report,
    save_report,
)

NAMES = ["a", "b", "c"]


def _report(matrix=None, instances=None):
    return build_class_report(
        NAMES,
        ap_class_index=[0, 1, 2],
        precision=[0.95, 0.40, 0.90],
        recall=[0.95, 0.15, 0.90],
        ap50=[0.96, 0.12, 0.91],
        ap50_95=[0.80, 0.08, 0.70],
        instances=instances or {0: 20, 1: 20, 2: 20},
        matrix=matrix,
    )


# matrix[predicted, true]; last row / column = background
MATRIX = np.array(
    [
        [19, 0, 0, 2],  # predicted a
        [0, 3, 6, 5],  # predicted b  (6 true c's were called b)
        [0, 0, 14, 0],  # predicted c
        [1, 17, 0, 0],  # predicted background (missed)
    ]
)


def test_rows_have_expected_fields_without_confusion_matrix() -> None:
    rows = _report()
    assert [r["class"] for r in rows] == NAMES
    assert rows[1]["recall"] == 0.15 and rows[1]["instances"] == 20
    assert "missed_rate" not in rows[0]


def test_confusion_matrix_adds_missed_confusion_and_false_alarms() -> None:
    rows = _report(MATRIX)
    b = rows[1]
    assert b["missed_rate"] == pytest.approx(17 / 20)  # 17 of 20 true b's seen as background
    assert rows[2]["main_confusion"] == "b"  # true c predicted as b
    assert rows[2]["main_confusion_rate"] == pytest.approx(6 / 20)
    assert b["false_positives"] == 11  # predicted b but true c (6) or background (5)
    assert rows[0]["main_confusion"] is None


def test_class_missing_from_validation_gets_zeros() -> None:
    rows = build_class_report(NAMES, [0], [0.9], [0.8], [0.85], [0.6], {0: 5})
    assert rows[2]["recall"] == 0.0 and rows[2]["instances"] == 0


def test_advice_flags_missed_and_false_alarm_classes() -> None:
    rows = _report(MATRIX)
    hints_b = " ".join(advice(rows[1]))
    assert "MISSED" in hints_b and "false alarms" in hints_b
    assert advice(rows[0]) == []
    assert "confused with b" in " ".join(advice(rows[2]))  # 30% >= 20% alert threshold


def test_advice_ignores_classes_absent_from_the_split() -> None:
    rows = _report(instances={0: 20, 1: 0, 2: 20})
    assert advice(rows[1]) == []


def test_format_report_markdown_and_save(tmp_path: Path) -> None:
    rows = _report(MATRIX)
    overall = {"precision": 0.75, "recall": 0.67, "mAP50": 0.66, "mAP50_95": 0.53}
    text = format_report(rows, overall, split="val", weights="runs/x/weights/best.pt")
    assert "| b | 20 | 0.40 | 0.15 |" in text
    assert "## Where to improve" in text and "**b**" in text

    md, js = save_report(rows, overall, tmp_path, "run1", split="val")
    assert md.name == "run1_val.md" and js.name == "run1_val.json"
    saved = json.loads(js.read_text())
    assert saved["overall"]["mAP50"] == 0.66 and len(saved["classes"]) == 3


def test_count_instances_reads_labels_next_to_images(tmp_path: Path) -> None:
    root = tmp_path / "images_project"  # a folder name containing "images" must not confuse it
    (root / "images" / "val").mkdir(parents=True)
    (root / "labels" / "val").mkdir(parents=True)
    (root / "labels" / "val" / "a.txt").write_text("0 0.5 0.5 0.1 0.1\n2 0.2 0.2 0.1 0.1\n")
    (root / "labels" / "val" / "b.txt").write_text("2 0.5 0.5 0.1 0.1\n")
    (root / "data.yaml").write_text("train: images/train\nval: images/val\nnc: 3\n")
    assert count_instances(root / "data.yaml", "val") == {0: 1, 2: 2}

    (root / "absolute.yaml").write_text(f'path: "{root.as_posix()}"\nval: images/val\n')
    assert count_instances(root / "absolute.yaml", "val") == {0: 1, 2: 2}


def test_generate_dataset_script_writes_a_balanced_yolo_dataset(tmp_path: Path) -> None:
    from generate_dataset import generate_dataset

    out = tmp_path / "ds"
    stats = generate_dataset(60, out, seed=1, bug_probability=0.9)
    assert len(list((out / "images" / "train").glob("*.png"))) == 42
    assert len(list((out / "labels" / "val").glob("*.txt"))) == 12
    yaml_text = (out / "data.yaml").read_text()
    assert "nc: 6" in yaml_text and "screen_tear" in yaml_text
    assert sum(stats["train"].values()) > 0
    assert count_instances(out / "data.yaml", "train") == dict(stats["train"])

    with pytest.raises(FileExistsError):  # never silently overwrite a dataset
        generate_dataset(10, out)
    generate_dataset(10, out, force=True)
    assert len(list((out / "images" / "train").glob("*.png"))) == 7
