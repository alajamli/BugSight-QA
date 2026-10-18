"""Unit tests for the training config."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.model.evaluate import DetectionMetrics  # noqa: E402
from src.model.trainer import TrainConfig, load_config  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "train.yaml"


def test_load_config_parses_all_fields() -> None:
    cfg = load_config(CONFIG_PATH)
    assert isinstance(cfg, TrainConfig)
    assert cfg.weights == "yolov8n.pt"
    assert cfg.task == "detect"
    assert cfg.epochs == 150
    assert cfg.device == "0"
    assert cfg.seed == 42


def test_to_train_kwargs_contains_required_keys() -> None:
    cfg = load_config(CONFIG_PATH)
    kwargs = cfg.to_train_kwargs()
    required = {"data", "epochs", "imgsz", "batch", "device", "seed", "optimizer"}
    assert required.issubset(kwargs.keys())


def test_train_kwargs_values_match_config() -> None:
    cfg = load_config(CONFIG_PATH)
    kwargs = cfg.to_train_kwargs()
    assert kwargs["lr0"] == 0.001
    assert kwargs["box"] == 7.5
    assert kwargs["mosaic"] == 1.0


def test_extra_regularisation_args_are_passed_through() -> None:
    kwargs = load_config(CONFIG_PATH).to_train_kwargs()
    assert kwargs["cos_lr"] is True
    assert kwargs["freeze"] == 10
    assert kwargs["close_mosaic"] == 15
    assert kwargs["degrees"] == 0.0


def test_detection_metrics_serialisation() -> None:
    m = DetectionMetrics(
        precision=0.92,
        recall=0.88,
        mAP50=0.90,
        mAP50_95=0.65,
        fitness=0.71,
        class_names=["floating_object"],
    )
    d = m.to_dict()
    assert d["precision"] == 0.92
    assert d["mAP50"] == 0.90
    assert d["class_names"] == ["floating_object"]


def test_config_cli_override_fields_writable() -> None:
    cfg = load_config(CONFIG_PATH)
    original = cfg.epochs
    cfg.epochs = 5
    assert cfg.epochs == 5
    assert cfg.epochs != original
