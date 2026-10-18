"""Training pipeline for the floating-object detector (YOLOv8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from ultralytics import YOLO


@dataclass
class TrainConfig:
    weights: str
    task: str
    data_yaml: str
    epochs: int
    imgsz: int
    batch: int
    patience: int
    optimizer: str
    lr0: float
    lrf: float
    momentum: float
    weight_decay: float
    warmup_epochs: int
    warmup_momentum: float
    box: float
    cls: float
    dfl: float
    hsv_h: float
    hsv_s: float
    hsv_v: float
    degrees: float
    translate: float
    scale: float
    fliplr: float
    mosaic: float
    mixup: float
    project: str
    name: str
    exist_ok: bool
    device: str
    workers: int
    seed: int
    # Optional Ultralytics arguments (cos_lr, close_mosaic, freeze, flipud,
    # erasing, dropout, ...) passed straight through, so tuning regularisation
    # only needs a YAML edit and no new dataclass field.
    extra: dict[str, Any] = field(default_factory=dict)

    def to_train_kwargs(self) -> dict[str, Any]:
        kwargs = {
            "data": self.data_yaml,
            "epochs": self.epochs,
            "imgsz": self.imgsz,
            "batch": self.batch,
            "patience": self.patience,
            "optimizer": self.optimizer,
            "lr0": self.lr0,
            "lrf": self.lrf,
            "momentum": self.momentum,
            "weight_decay": self.weight_decay,
            "warmup_epochs": self.warmup_epochs,
            "warmup_momentum": self.warmup_momentum,
            "box": self.box,
            "cls": self.cls,
            "dfl": self.dfl,
            "hsv_h": self.hsv_h,
            "hsv_s": self.hsv_s,
            "hsv_v": self.hsv_v,
            "degrees": self.degrees,
            "translate": self.translate,
            "scale": self.scale,
            "fliplr": self.fliplr,
            "mosaic": self.mosaic,
            "mixup": self.mixup,
            "project": self.project,
            "name": self.name,
            "exist_ok": self.exist_ok,
            "device": self.device,
            "workers": self.workers,
            "seed": self.seed,
        }
        kwargs.update(self.extra)
        return kwargs


def load_config(config_path: str | Path) -> TrainConfig:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    return TrainConfig(
        weights=cfg["model"]["weights"],
        task=cfg["model"]["task"],
        data_yaml=cfg["data"]["yaml"],
        epochs=cfg["train"]["epochs"],
        imgsz=cfg["train"]["imgsz"],
        batch=cfg["train"]["batch"],
        patience=cfg["train"]["patience"],
        optimizer=cfg["train"]["optimizer"],
        lr0=cfg["train"]["lr0"],
        lrf=cfg["train"]["lrf"],
        momentum=cfg["train"]["momentum"],
        weight_decay=cfg["train"]["weight_decay"],
        warmup_epochs=cfg["train"]["warmup_epochs"],
        warmup_momentum=cfg["train"]["warmup_momentum"],
        box=cfg["train"]["box"],
        cls=cfg["train"]["cls"],
        dfl=cfg["train"]["dfl"],
        hsv_h=cfg["augment"]["hsv_h"],
        hsv_s=cfg["augment"]["hsv_s"],
        hsv_v=cfg["augment"]["hsv_v"],
        degrees=cfg["augment"]["degrees"],
        translate=cfg["augment"]["translate"],
        scale=cfg["augment"]["scale"],
        fliplr=cfg["augment"]["fliplr"],
        mosaic=cfg["augment"]["mosaic"],
        mixup=cfg["augment"]["mixup"],
        project=cfg["output"]["project"],
        name=cfg["output"]["name"],
        exist_ok=cfg["output"]["exist_ok"],
        device=cfg["device"],
        workers=cfg["workers"],
        seed=cfg["seed"],
        extra=cfg.get("extra") or {},
    )


def _find_best_weights(cfg: TrainConfig) -> str:
    base = Path(cfg.project)
    candidates = list(base.rglob("best.pt"))
    if not candidates:
        raise FileNotFoundError(f"No best.pt found under {base}.")
    best = max(candidates, key=lambda p: p.stat().st_mtime)
    return str(best)


def train_model(config_path: str | Path) -> str:
    cfg = load_config(config_path)
    model = YOLO(cfg.weights)
    model.train(**cfg.to_train_kwargs())
    return _find_best_weights(cfg)
