"""Evaluation utilities for the trained YOLOv8 detector."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ultralytics import YOLO


@dataclass
class DetectionMetrics:
    precision: float
    recall: float
    mAP50: float
    mAP50_95: float
    fitness: float
    class_names: list[str]
    # Per-class AP50 - with ~6-20 test boxes per class the global mAP hides
    # which bug types the model actually misses.
    per_class_ap50: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "mAP50": round(self.mAP50, 4),
            "mAP50_95": round(self.mAP50_95, 4),
            "fitness": round(self.fitness, 4),
            "class_names": self.class_names,
        }
        if self.per_class_ap50:
            d["per_class_ap50"] = {k: round(v, 4) for k, v in self.per_class_ap50.items()}
        return d


def evaluate_model(
    weights_path: str | Path,
    data_yaml: str | Path,
    *,
    device: str = "cpu",
    imgsz: int = 640,
    batch: int = 16,
    split: str = "test",
) -> DetectionMetrics:
    model = YOLO(str(weights_path))
    results = model.val(
        data=str(data_yaml),
        split=split,
        device=device,
        imgsz=imgsz,
        batch=batch,
        verbose=False,
    )
    box = results.box
    names = list(results.names.values()) if hasattr(results, "names") else ["floating_object"]
    per_class = {
        results.names[int(c)]: float(ap)
        for c, ap in zip(box.ap_class_index, box.ap50, strict=False)
    }
    return DetectionMetrics(
        per_class_ap50=per_class,
        precision=float(box.mp),
        recall=float(box.mr),
        mAP50=float(box.map50),
        mAP50_95=float(box.map),
        fitness=float(results.fitness),
        class_names=names,
    )


def predict_image(
    weights_path: str | Path,
    image_path: str | Path,
    *,
    conf: float = 0.25,
    device: str = "cpu",
) -> dict[str, Any]:
    model = YOLO(str(weights_path))
    results = model.predict(source=str(image_path), conf=conf, device=device, verbose=False)
    if not results:
        return {"detections": [], "num_detections": 0, "has_bug": False}

    r = results[0]
    detections = []
    if r.boxes is not None and len(r.boxes) > 0:
        for box in r.boxes:
            xyxy = box.xyxy[0].tolist()
            detections.append(
                {
                    "class_id": int(box.cls[0]),
                    "class_name": r.names[int(box.cls[0])],
                    "confidence": round(float(box.conf[0]), 4),
                    "bbox_xyxy": [round(v, 2) for v in xyxy],
                }
            )
    return {
        "detections": detections,
        "num_detections": len(detections),
        "has_bug": len(detections) > 0,
    }
