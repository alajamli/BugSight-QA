"""Unit tests for the semi-synthetic (real background) scene generator."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_generation.scene_generator import CLASS_NAMES  # noqa: E402
from src.data_generation.semi_synthetic import (  # noqa: E402
    RealSceneConfig,
    RealSceneGenerator,
    split_backgrounds,
)


def _fake_screenshot(seed: int) -> np.ndarray:
    """Textured 16:9 image standing in for a real screenshot."""
    rng = np.random.default_rng(seed)
    yy, xx = np.indices((360, 640))
    base = np.stack([(xx * 0.3) % 255, (yy * 0.5) % 255, ((xx + yy) * 0.2) % 255], axis=2)
    blocks = rng.integers(0, 120, (9, 16, 3)).repeat(40, axis=0).repeat(40, axis=1)
    return ((base + blocks) % 256).astype(np.uint8)


@pytest.fixture
def backgrounds() -> list[np.ndarray]:
    return [_fake_screenshot(i) for i in range(3)]


def test_output_size(backgrounds) -> None:
    gen = RealSceneGenerator(backgrounds, RealSceneConfig(seed=0))
    assert gen.generate().image.shape == (360, 640, 3)


def test_deterministic_with_seed(backgrounds) -> None:
    gen1 = RealSceneGenerator(backgrounds, RealSceneConfig(seed=5))
    gen2 = RealSceneGenerator(backgrounds, RealSceneConfig(seed=5))
    for _ in range(3):
        s1, s2 = gen1.generate(), gen2.generate()
        assert np.array_equal(s1.image, s2.image)
        assert [a.to_yolo_line() for a in s1.annotations] == [
            a.to_yolo_line() for a in s2.annotations
        ]


def test_clean_scenes_have_no_labels(backgrounds) -> None:
    gen = RealSceneGenerator(backgrounds, RealSceneConfig(seed=1, bug_probability=0.0))
    for _ in range(5):
        assert not gen.generate().annotations


@pytest.mark.parametrize("class_id", range(len(CLASS_NAMES)))
def test_every_class_is_placed_and_visible(backgrounds, class_id: int) -> None:
    cfg = RealSceneConfig(seed=class_id, degrade_probability=0.0)
    gen = RealSceneGenerator(backgrounds, cfg)
    for _ in range(5):
        sample = gen.generate(classes=[class_id])
        assert [a.class_id for a in sample.annotations] == [class_id]
        a = sample.annotations[0]
        assert 0 < a.w <= 1 and 0 < a.h <= 1
        assert 0 <= a.cx - a.w / 2 and a.cx + a.w / 2 <= 1
        assert 0 <= a.cy - a.h / 2 and a.cy + a.h / 2 <= 1
        x1 = int(round((a.cx - a.w / 2) * cfg.width))
        x2 = int(round((a.cx + a.w / 2) * cfg.width))
        y1 = int(round((a.cy - a.h / 2) * cfg.height))
        y2 = int(round((a.cy + a.h / 2) * cfg.height))
        changed = np.abs(
            sample.image[y1:y2, x1:x2].astype(np.int16)
            - sample.clean_image[y1:y2, x1:x2].astype(np.int16)
        )
        assert changed.mean() > 3, "the labelled box must contain a visible defect"


def test_reads_background_files(tmp_path, backgrounds) -> None:
    import cv2

    path = tmp_path / "shot.jpg"
    cv2.imwrite(str(path), backgrounds[0])
    gen = RealSceneGenerator(config=RealSceneConfig(seed=0))
    assert gen.generate(background=path).image.shape == (360, 640, 3)


def test_requires_backgrounds() -> None:
    with pytest.raises(ValueError):
        RealSceneGenerator().generate()


def test_split_has_no_leakage_and_holdout() -> None:
    groups = {g: [Path(f"{g}/{i}.jpg") for i in range(50)] for g in ("a", "b", "c")}
    splits = split_backgrounds(groups, {"train": 0.7, "val": 0.2, "test": 0.1}, holdout=["c"])
    seen = [p for paths in splits.values() for p in paths]
    assert len(seen) == len(set(seen)) == 150
    assert all(p.parent.name == "c" for p in splits["test"][-50:])
    assert not any(p.parent.name == "c" for p in splits["train"] + splits["val"])


def test_uniform_backgrounds_are_rejected(backgrounds) -> None:
    from src.data_generation.semi_synthetic import is_usable_background

    assert is_usable_background(backgrounds[0])
    assert not is_usable_background(np.zeros((360, 640, 3), np.uint8))
    assert not is_usable_background(None)
