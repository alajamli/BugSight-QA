"""Unit tests for the synthetic scene generator."""

from __future__ import annotations

import collections
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_generation.scene_generator import (  # noqa: E402
    CLASS_NAMES,
    SceneConfig,
    SceneGenerator,
)


@pytest.fixture
def generator() -> SceneGenerator:
    return SceneGenerator(SceneConfig(seed=0))


def test_image_shape(generator: SceneGenerator) -> None:
    sample = generator.generate()
    assert sample.image.shape == (640, 640, 3)


def test_deterministic_with_seed() -> None:
    gen1 = SceneGenerator(SceneConfig(seed=123))
    gen2 = SceneGenerator(SceneConfig(seed=123))
    for _ in range(3):
        s1 = gen1.generate()
        s2 = gen2.generate()
        assert np.array_equal(s1.image, s2.image)
        assert len(s1.annotations) == len(s2.annotations)


def test_successive_samples_differ() -> None:
    # A seeded generator must still produce a *different* scene each call
    # (re-seeding on every call used to make a whole dataset identical).
    gen = SceneGenerator(SceneConfig(seed=7))
    first = gen.generate().image
    second = gen.generate().image
    assert not np.array_equal(first, second)


def test_bug_probability_respected() -> None:
    clean = SceneGenerator(SceneConfig(seed=1, bug_probability=0.0))
    buggy = SceneGenerator(SceneConfig(seed=1, bug_probability=1.0))
    for _ in range(20):
        c = clean.generate()
        assert not c.has_bug and not c.annotations
        b = buggy.generate()
        assert b.has_bug and b.annotations


def test_annotations_are_yolo_normalized(generator: SceneGenerator) -> None:
    for _ in range(10):
        sample = generator.generate()
        for ann in sample.annotations:
            assert 0.0 <= ann.cx <= 1.0
            assert 0.0 <= ann.cy <= 1.0
            assert 0.0 < ann.w <= 1.0
            assert 0.0 < ann.h <= 1.0
            assert 0.0 <= ann.cx - ann.w / 2 and ann.cx + ann.w / 2 <= 1.0 + 1e-6
            assert 0.0 <= ann.cy - ann.h / 2 and ann.cy + ann.h / 2 <= 1.0 + 1e-6
            assert 0 <= ann.class_id < len(CLASS_NAMES)


def test_yolo_line_format(generator: SceneGenerator) -> None:
    sample = SceneGenerator(SceneConfig(seed=2, bug_probability=1.0)).generate()
    for ann in sample.annotations:
        parts = ann.to_yolo_line().split()
        assert len(parts) == 5
        assert parts[0].isdigit()
        assert 0 <= int(parts[0]) < len(CLASS_NAMES)
        assert all(0.0 <= float(p) <= 1.0 for p in parts[1:])


def test_save_creates_files(tmp_path: Path) -> None:
    sample = SceneGenerator(SceneConfig(seed=3, bug_probability=1.0)).generate()
    img_path = tmp_path / "images" / "sample.png"
    lbl_path = tmp_path / "labels" / "sample.txt"
    sample.save(img_path, lbl_path)
    assert img_path.exists()
    assert lbl_path.exists()
    n_bugs = sum(1 for a in sample.annotations if a.is_bug)
    assert len(lbl_path.read_text().strip().splitlines()) == n_bugs


def test_class_names_match_the_six_product_classes() -> None:
    assert CLASS_NAMES == [
        "missing_texture",
        "texture_glitch",
        "z_fighting",
        "screen_tear",
        "uv_stretch",
        "color_corruption",
    ]


@pytest.mark.parametrize("class_id", range(len(CLASS_NAMES)))
def test_every_class_is_visibly_rendered(class_id: int) -> None:
    """The labelled box must really differ from the clean scene."""
    cfg = SceneConfig(seed=100 + class_id)
    gen = SceneGenerator(cfg)
    for _ in range(15):
        sample = gen.generate(classes=[class_id])
        assert [a.class_id for a in sample.annotations] == [class_id]
        ann = sample.annotations[0]
        h, w = sample.image.shape[:2]
        x1, x2 = int((ann.cx - ann.w / 2) * w + 0.5), int((ann.cx + ann.w / 2) * w + 0.5)
        y1, y2 = int((ann.cy - ann.h / 2) * h + 0.5), int((ann.cy + ann.h / 2) * h + 0.5)
        change = np.abs(
            sample.image[y1:y2, x1:x2].astype(np.int16)
            - sample.clean_image[y1:y2, x1:x2].astype(np.int16)
        ).mean()
        assert change >= cfg.min_visibility - 1.0, (CLASS_NAMES[class_id], change)
        # nothing outside the box was modified
        outside = sample.image.copy()
        outside[y1:y2, x1:x2] = sample.clean_image[y1:y2, x1:x2]
        assert np.array_equal(outside, sample.clean_image)


def test_classes_are_balanced_over_a_dataset() -> None:
    gen = SceneGenerator(SceneConfig(seed=5, bug_probability=0.8))
    counts: collections.Counter[int] = collections.Counter()
    for _ in range(300):
        counts.update(a.class_id for a in gen.generate().annotations)
    assert set(counts) == set(range(len(CLASS_NAMES)))
    assert max(counts.values()) / min(counts.values()) < 1.6
