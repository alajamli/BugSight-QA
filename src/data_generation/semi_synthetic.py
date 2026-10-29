"""Semi-synthetic scenes: the six BugSight defects drawn on real gameplay screenshots.

The fully synthetic generator (``scene_generator.py``) paints defects on flat
coloured rectangles, so a model trained on it learns "anything textured is a
bug" and fails on real games. This generator keeps the same six defect
renderers but:

- uses real screenshots as backgrounds (natural textures such as Minecraft
  blocks or Terraria pixel art become hard negatives),
- lets most defects follow an irregular shape (a surface found by flood fill,
  or a random blob) instead of a perfect rectangle, with the label set to the
  tight box around the shape,
- keeps the scene's lighting on flat defects (missing texture, z-fighting),
- draws screen tears across the frame without the artificial bright seam,
- degrades the whole frame like a real capture (JPEG, blur, noise, exposure,
  resolution loss).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from src.data_generation.scene_generator import (
    MISSING_TEXTURE_CLASS_ID,
    SCREEN_TEAR_CLASS_ID,
    Z_FIGHTING_CLASS_ID,
    Box,
    SceneConfig,
    SceneGenerator,
    SceneSample,
)

Background = str | Path | np.ndarray

# Flat-colour defects that look pasted-on unless the scene lighting is kept.
_SHADED_CLASSES = {MISSING_TEXTURE_CLASS_ID, Z_FIGHTING_CLASS_ID}


@dataclass
class RealSceneConfig(SceneConfig):
    width: int = 640
    height: int = 360
    bug_probability: float = 0.7
    min_defect_size: int = 40
    max_defect_size: int = 150
    # Defect follows an irregular / surface mask instead of filling its box.
    shaped_probability: float = 0.6
    # Scene lighting multiplied into flat-colour defects.
    shading_probability: float = 0.5
    # Screen tear spans the whole frame width (as on a real display).
    full_width_tear_probability: float = 0.5
    # Capture artefacts (JPEG, blur, noise, exposure) on the whole frame.
    degrade_probability: float = 0.8
    # Smallest side of a shaped defect's tight box, in pixels.
    min_shaped_side: int = 20


class RealSceneGenerator(SceneGenerator):
    """Draw labelled defects on real screenshots.

    ``backgrounds`` are image paths or BGR arrays; ``generate(background=...)``
    picks one explicitly (used to keep each background in a single split),
    otherwise one is chosen at random.
    """

    def __init__(
        self, backgrounds: Sequence[Background] = (), config: RealSceneConfig | None = None
    ) -> None:
        super().__init__(config or RealSceneConfig())
        self.config: RealSceneConfig
        self.backgrounds = list(backgrounds)
        self._background: Background | None = None
        self._appliers[SCREEN_TEAR_CLASS_ID] = self._real_screen_tear

    # ── public API ─────────────────────────────────────────────

    def generate(
        self, classes: Sequence[int] | None = None, background: Background | None = None
    ) -> SceneSample:
        if background is None and not self.backgrounds:
            raise ValueError("RealSceneGenerator needs at least one background image.")
        self._background = background
        sample = super().generate(classes)
        if self.rng.random() < self.config.degrade_probability:
            sample.image = self._degrade(sample.image)
        return sample

    # ── scene ──────────────────────────────────────────────────

    def _draw_scene(self) -> np.ndarray:
        source = (
            self._background if self._background is not None else self.rng.choice(self.backgrounds)
        )
        if isinstance(source, np.ndarray):
            image = source.copy()
        else:
            image = cv2.imread(str(source), cv2.IMREAD_COLOR)
            if image is None:
                raise FileNotFoundError(f"Cannot read background image {source}")
        return self._fit(image)

    def _fit(self, image: np.ndarray) -> np.ndarray:
        """Random crop to the target aspect ratio (sometimes zoomed), flip, resize."""
        cfg = self.config
        h, w = image.shape[:2]
        target = cfg.width / cfg.height
        crop_w, crop_h = (int(h * target), h) if w / h > target else (w, int(w / target))
        if self.rng.random() < 0.4:
            zoom = self.rng.uniform(0.7, 1.0)
            crop_w, crop_h = int(crop_w * zoom), int(crop_h * zoom)
        x1 = self.rng.randint(0, w - crop_w)
        y1 = self.rng.randint(0, h - crop_h)
        image = image[y1 : y1 + crop_h, x1 : x1 + crop_w]
        if self.rng.random() < 0.5:
            image = image[:, ::-1]
        interpolation = cv2.INTER_AREA if crop_w >= cfg.width else cv2.INTER_LINEAR
        return np.ascontiguousarray(
            cv2.resize(image, (cfg.width, cfg.height), interpolation=interpolation)
        )

    # ── placement ──────────────────────────────────────────────

    def _box_for(self, class_id: int) -> Box:
        cfg = self.config
        if class_id == SCREEN_TEAR_CLASS_ID:
            if self.rng.random() < cfg.full_width_tear_probability:
                width = (cfg.width, cfg.width)
            else:
                width = (int(cfg.width * 0.4), int(cfg.width * 0.9))
            return self._random_box(width, (30, 80))
        return self._random_box(
            (cfg.min_defect_size, cfg.max_defect_size),
            (cfg.min_defect_size, cfg.max_defect_size),
        )

    def _place_defect(self, image, class_id, taken):
        cfg = self.config
        apply = self._appliers[class_id]
        for _ in range(40):
            box = self._box_for(class_id)
            if self._overlaps(box, taken):
                continue
            x1, y1, x2, y2 = box
            before = image[y1:y2, x1:x2]
            after = apply(before, image)
            if after is None:
                continue
            if class_id in _SHADED_CLASSES and self.rng.random() < cfg.shading_probability:
                after = self._keep_lighting(after, before)

            mask = None
            if class_id != SCREEN_TEAR_CLASS_ID and self.rng.random() < cfg.shaped_probability:
                mask = self._shape_mask(before)
            if mask is None:
                patch, inside = after, np.ones(before.shape[:2], bool)
            else:
                alpha = mask[..., None]
                patch = (after * alpha + before * (1 - alpha)).astype(np.uint8)
                inside = mask > 0.5

            diff = np.abs(patch.astype(np.int16) - before.astype(np.int16)).mean(axis=2)
            if float(diff[inside].mean()) < cfg.min_visibility:
                continue
            image[y1:y2, x1:x2] = patch

            if mask is not None:  # label the shape, not the whole search box
                ys, xs = np.nonzero(inside)
                box = (
                    x1 + int(xs.min()),
                    y1 + int(ys.min()),
                    x1 + int(xs.max()) + 1,
                    y1 + int(ys.max()) + 1,
                )
            return box, self._annotation(class_id, box)
        return None

    def _shape_mask(self, patch: np.ndarray) -> np.ndarray | None:
        """Soft mask in [0, 1]: a surface of similar colour, else a random blob."""
        h, w = patch.shape[:2]
        mask = self._surface_mask(patch) if self.rng.random() < 0.5 else None
        if mask is None:
            mask = self._blob_mask(h, w)
        inside = mask > 127
        ys, xs = np.nonzero(inside)
        if len(ys) == 0:
            return None
        side = self.config.min_shaped_side
        if ys.max() - ys.min() + 1 < side or xs.max() - xs.min() + 1 < side:
            return None
        return cv2.GaussianBlur(mask, (3, 3), 0).astype(np.float32) / 255.0

    def _surface_mask(self, patch: np.ndarray) -> np.ndarray | None:
        """Flood-fill a surface from a point near the centre (e.g. one wall or object)."""
        h, w = patch.shape[:2]
        smooth = cv2.GaussianBlur(patch, (5, 5), 0)
        seed = (
            self.rng.randint(w // 3, max(w // 3, 2 * w // 3)),
            self.rng.randint(h // 3, max(h // 3, 2 * h // 3)),
        )
        tol = (self.rng.randint(10, 24),) * 3
        flood = np.zeros((h + 2, w + 2), np.uint8)
        flags = 8 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
        cv2.floodFill(smooth, flood, seed, (0, 0, 0), tol, tol, flags)
        mask = flood[1:-1, 1:-1]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        if (mask > 0).mean() < 0.25:  # too small to be a readable defect
            return None
        return mask

    def _blob_mask(self, h: int, w: int) -> np.ndarray:
        """Irregular polygon roughly filling the box."""
        n = self.rng.randint(6, 11)
        angles = np.sort(self.np_rng.uniform(0, 2 * np.pi, n))
        radii = self.np_rng.uniform(0.6, 1.0, n)
        cx, cy = w / 2, h / 2
        points = np.stack(
            [cx + np.cos(angles) * radii * (w / 2 - 1), cy + np.sin(angles) * radii * (h / 2 - 1)],
            axis=1,
        ).astype(np.int32)
        mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask, [points], 255)
        return mask

    # ── defects ────────────────────────────────────────────────

    @staticmethod
    def _keep_lighting(after: np.ndarray, before: np.ndarray) -> np.ndarray:
        """Multiply the scene's shading into a flat defect so it sits on the surface."""
        gray = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY).astype(np.float32)
        light = np.clip(gray / (gray.mean() + 1e-3), 0.5, 1.5)[..., None]
        return np.clip(after * (0.5 + 0.5 * light), 0, 255).astype(np.uint8)

    def _real_screen_tear(self, patch: np.ndarray, image: np.ndarray) -> np.ndarray | None:
        """Upper part of the band comes from a horizontally shifted frame; no seam line."""
        h, w = patch.shape[:2]
        tear_row = self.rng.randint(h // 3, 2 * h // 3)
        dx = self.rng.choice((-1, 1)) * self.rng.randint(12, 50)
        shift = np.float32([[1, 0, dx], [0, 1, 0]])
        top = cv2.warpAffine(
            patch[:tear_row], shift, (w, tear_row), borderMode=cv2.BORDER_REPLICATE
        )
        if self.rng.random() < 0.4:  # the other frame can be slightly brighter or darker
            top = cv2.convertScaleAbs(top, alpha=1.0, beta=self.rng.randint(-18, 18))
        displacement = np.abs(top.astype(np.int16) - patch[:tear_row].astype(np.int16)).mean()
        if displacement < 10:  # flat area: the tear would not be visible
            return None
        out = patch.copy()
        out[:tear_row] = top
        return out

    # ── capture artefacts ──────────────────────────────────────

    def _degrade(self, image: np.ndarray) -> np.ndarray:
        cfg = self.config
        if self.rng.random() < 0.5:  # exposure / contrast
            image = cv2.convertScaleAbs(
                image, alpha=self.rng.uniform(0.8, 1.2), beta=self.rng.randint(-20, 20)
            )
        if self.rng.random() < 0.3:  # streamed / upscaled capture
            factor = self.rng.uniform(0.5, 0.85)
            small = cv2.resize(image, (int(cfg.width * factor), int(cfg.height * factor)))
            image = cv2.resize(small, (cfg.width, cfg.height), interpolation=cv2.INTER_LINEAR)
        if self.rng.random() < 0.25:
            image = cv2.GaussianBlur(image, (3, 3), 0)
        if self.rng.random() < 0.3:
            noise = self.np_rng.normal(0, self.rng.uniform(2, 6), image.shape)
            image = np.clip(image + noise, 0, 255).astype(np.uint8)
        if self.rng.random() < 0.6:
            quality = self.rng.randint(40, 90)
            ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if ok:
                image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return image


def is_usable_background(image: np.ndarray | None, min_std: float = 20.0) -> bool:
    """False for unreadable or near-uniform frames (black loading screens, fades)."""
    if image is None:
        return False
    return float(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).std()) >= min_std


def split_backgrounds(
    groups: dict[str, list[Path]],
    fractions: dict[str, float],
    seed: int = 42,
    holdout: Sequence[str] = (),
) -> dict[str, list[Path]]:
    """Split backgrounds per group (game) so no screenshot appears in two splits.

    Groups listed in ``holdout`` go entirely to ``test`` (unseen games), and
    are left out of train / val.
    """
    rng = random.Random(seed)
    splits: dict[str, list[Path]] = {name: [] for name in fractions}
    for group in sorted(groups):
        items = sorted(groups[group])
        if group in holdout:
            splits["test"].extend(items)
            continue
        rng.shuffle(items)
        n_train = round(len(items) * fractions["train"])
        n_val = round(len(items) * fractions["val"])
        splits["train"].extend(items[:n_train])
        splits["val"].extend(items[n_train : n_train + n_val])
        splits["test"].extend(items[n_train + n_val :])
    return splits
