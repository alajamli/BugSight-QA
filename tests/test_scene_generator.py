"""Unit tests for the synthetic scene generator."""

from __future__ import annotations

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
    assert sample.image.shape == (480, 640, 3)


def test_deterministic_with_seed() -> None:
    gen1 = SceneGenerator(SceneConfig(seed=123))
    gen2 = SceneGenerator(SceneConfig(seed=123))
    s1 = gen1.generate()
    s2 = gen2.generate()
    assert np.array_equal(s1.image, s2.image)
    assert len(s1.annotations) == len(s2.annotations)


def test_bug_probability_respected() -> None:
    clean = SceneGenerator(SceneConfig(seed=1, bug_probability=0.0))
    buggy = SceneGenerator(SceneConfig(seed=1, bug_probability=1.0))
    for _ in range(20):
        assert not clean.generate().has_bug
        assert buggy.generate().has_bug


def test_annotations_are_yolo_normalized(generator: SceneGenerator) -> None:
    sample = generator.generate()
    for ann in sample.annotations:
        assert 0.0 <= ann.cx <= 1.0
        assert 0.0 <= ann.cy <= 1.0
        assert 0.0 < ann.w <= 1.0
        assert 0.0 < ann.h <= 1.0
        # The generator now produces several bug classes (not just
        # "floating_object"), so any valid class index is acceptable here.
        assert 0 <= ann.class_id < len(CLASS_NAMES)


def test_yolo_line_format(generator: SceneGenerator) -> None:
    sample = generator.generate()
    for ann in sample.annotations:
        parts = ann.to_yolo_line().split()
        assert len(parts) == 5
        assert parts[0].isdigit()
        assert 0 <= int(parts[0]) < len(CLASS_NAMES)
        assert all(0.0 <= float(p) <= 1.0 for p in parts[1:])


def test_save_creates_files(tmp_path: Path, generator: SceneGenerator) -> None:
    sample = generator.generate()
    img_path = tmp_path / "images" / "sample.png"
    lbl_path = tmp_path / "labels" / "sample.txt"
    sample.save(img_path, lbl_path)
    assert img_path.exists()
    assert lbl_path.exists()
    n_bugs = sum(1 for a in sample.annotations if a.is_bug)
    assert len(lbl_path.read_text().strip().splitlines()) == n_bugs


def test_class_names_cover_all_bug_types() -> None:
    # Was a "singleton" check from an earlier version of the generator that
    # only produced one bug class; it now produces several, so we assert the
    # invariants that still matter: non-empty, unique, and every generated
    # annotation's class_id resolves to a name in this list.
    assert len(CLASS_NAMES) >= 1
    assert len(CLASS_NAMES) == len(set(CLASS_NAMES))
    assert "floating_object" in CLASS_NAMES
