"""Unit tests for the training configs."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.model.evaluate import DetectionMetrics  # noqa: E402
from src.model.trainer import TrainConfig, load_config  # noqa: E402

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"
CONFIG_PATH = CONFIG_DIR / "train.yaml"
GPU_CONFIG_PATH = CONFIG_DIR / "train_gpu.yaml"


def test_load_config_parses_all_fields() -> None:
    cfg = load_config(CONFIG_PATH)
    assert isinstance(cfg, TrainConfig)
    assert cfg.weights == "yolov8n.pt"
    assert cfg.task == "detect"
    assert cfg.data_yaml == "data/processed_v2/data.yaml"
    assert cfg.seed == 42


def test_default_config_runs_on_cpu_only_machines() -> None:
    # The default must not require CUDA: a "0" device crashes on CPU-only PyTorch.
    assert load_config(CONFIG_PATH).device == "cpu"


def test_gpu_config_targets_the_gpu() -> None:
    cfg = load_config(GPU_CONFIG_PATH)
    assert cfg.device == "0"
    assert cfg.imgsz == 640
    assert cfg.weights == "yolov8s.pt"


@pytest.mark.parametrize("path", [CONFIG_PATH, GPU_CONFIG_PATH])
def test_to_train_kwargs_contains_required_keys(path: Path) -> None:
    kwargs = load_config(path).to_train_kwargs()
    required = {"data", "epochs", "imgsz", "batch", "device", "seed", "optimizer"}
    assert required.issubset(kwargs.keys())


@pytest.mark.parametrize("path", [CONFIG_PATH, GPU_CONFIG_PATH])
def test_augmentation_protects_colour_and_defect_signal(path: Path) -> None:
    kwargs = load_config(path).to_train_kwargs()
    # colour is the signal for color_corruption / missing_texture
    assert kwargs["hsv_h"] == 0.0
    # mixup / random erasing paint or blend fake defects
    assert kwargs["mixup"] == 0.0
    assert kwargs["erasing"] == 0.0
    assert kwargs["degrees"] == 0.0
    assert kwargs["flipud"] == 0.0
    assert "freeze" not in kwargs  # the backbone is trained on the synthetic domain


def test_extra_args_are_passed_through() -> None:
    kwargs = load_config(CONFIG_PATH).to_train_kwargs()
    assert kwargs["cos_lr"] is True
    assert kwargs["close_mosaic"] == 8
    assert kwargs["cache"] == "ram"


def test_detection_metrics_serialisation() -> None:
    m = DetectionMetrics(
        precision=0.92,
        recall=0.88,
        mAP50=0.90,
        mAP50_95=0.65,
        fitness=0.71,
        class_names=["missing_texture"],
        per_class=[{"class": "missing_texture", "recall": 0.9}],
    )
    d = m.to_dict()
    assert d["precision"] == 0.92
    assert d["mAP50"] == 0.90
    assert d["class_names"] == ["missing_texture"]
    assert d["per_class"][0]["recall"] == 0.9
    assert m.overall()["recall"] == 0.88


def test_config_cli_override_fields_writable() -> None:
    cfg = load_config(CONFIG_PATH)
    original = cfg.epochs
    cfg.epochs = 5
    assert cfg.epochs == 5
    assert cfg.epochs != original
