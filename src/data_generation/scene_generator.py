"""Synthetic scene generator for the six BugSight bug classes.

Every labelled defect is *visibly rendered* inside its bounding box, and the
generator checks that the box really differs from the clean scene (mean pixel
change >= ``SceneConfig.min_visibility``) before it keeps the label. An earlier
dataset labelled "screen_tear" and "uv_stretch" boxes over regions that looked
identical to the background, which capped recall for those classes at 10-25%
no matter how the model was tuned.

Classes (same order as ``data.yaml`` and the API):

- missing_texture   magenta / black checkerboard
- texture_glitch    per-pixel noise or blocky colour artefacts
- z_fighting        two colours flickering in thin stripes
- screen_tear       a band of the image shifted sideways with a bright seam
- uv_stretch        a few colours smeared into streaks along one axis
- color_corruption  inverted / channel-swapped / hue-rotated region, or a flat
                    wrong-colour block
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

CLASS_NAMES = [
    "missing_texture",
    "texture_glitch",
    "z_fighting",
    "screen_tear",
    "uv_stretch",
    "color_corruption",
]
MISSING_TEXTURE_CLASS_ID = 0
TEXTURE_GLITCH_CLASS_ID = 1
Z_FIGHTING_CLASS_ID = 2
SCREEN_TEAR_CLASS_ID = 3
UV_STRETCH_CLASS_ID = 4
COLOR_CORRUPTION_CLASS_ID = 5

# BGR colours used for stripes / flat corruption blocks
_PALETTE = (
    (40, 200, 200),
    (60, 160, 60),
    (200, 160, 40),
    (200, 200, 200),
    (30, 30, 30),
    (0, 0, 200),
    (200, 60, 120),
)
_WRONG_COLOURS = ((255, 255, 0), (0, 255, 128), (0, 128, 255), (255, 0, 160), (0, 255, 255))


@dataclass
class SceneConfig:
    width: int = 640
    height: int = 640
    horizon_ratio: float = 0.5
    bug_probability: float = 0.5
    min_bugs: int = 1
    max_bugs: int = 3
    min_buildings: int = 4
    max_buildings: int = 9
    min_defect_size: int = 56
    max_defect_size: int = 150
    # Minimum mean absolute pixel change inside a defect box; below this the
    # defect is considered invisible and is re-rolled somewhere else.
    min_visibility: float = 10.0
    seed: int | None = None


@dataclass
class Annotation:
    class_id: int
    cx: float
    cy: float
    w: float
    h: float
    is_bug: bool = False

    def to_yolo_line(self) -> str:
        return f"{self.class_id} {self.cx:.6f} {self.cy:.6f} {self.w:.6f} {self.h:.6f}"


@dataclass
class SceneSample:
    image: np.ndarray
    annotations: list[Annotation] = field(default_factory=list)
    has_bug: bool = False
    # The same scene before any defect was drawn (used by tests / debugging).
    clean_image: np.ndarray | None = None

    def save(self, image_path: Path, label_path: Path) -> None:
        image_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(image_path), self.image)
        lines = [a.to_yolo_line() for a in self.annotations if a.is_bug]
        label_path.write_text("\n".join(lines) + ("\n" if lines else ""))


Box = tuple[int, int, int, int]  # x1, y1, x2, y2 (pixels)


class SceneGenerator:
    """Generate synthetic game scenes with visible, labelled rendering bugs.

    Successive ``generate()`` calls produce different scenes; two generators
    built with the same seed produce the same sequence.
    """

    def __init__(self, config: SceneConfig | None = None) -> None:
        self.config = config or SceneConfig()
        self.rng = random.Random(self.config.seed)
        self.np_rng = np.random.default_rng(self.config.seed)
        self._appliers: dict[int, Callable[[np.ndarray, np.ndarray], np.ndarray | None]] = {
            MISSING_TEXTURE_CLASS_ID: self._missing_texture,
            TEXTURE_GLITCH_CLASS_ID: self._texture_glitch,
            Z_FIGHTING_CLASS_ID: self._z_fighting,
            SCREEN_TEAR_CLASS_ID: self._screen_tear,
            UV_STRETCH_CLASS_ID: self._uv_stretch,
            COLOR_CORRUPTION_CLASS_ID: self._color_corruption,
        }

    # ── public API ─────────────────────────────────────────────

    def generate(self, classes: Sequence[int] | None = None) -> SceneSample:
        """Render one scene.

        ``classes`` forces exactly those defect classes (handy for tests and for
        building class-balanced sets); otherwise defects are drawn at random
        according to ``bug_probability``.
        """
        cfg = self.config
        image = self._draw_scene()
        clean = image.copy()
        annotations: list[Annotation] = []

        if classes is not None:
            wanted = list(classes)
        elif self.rng.random() < cfg.bug_probability:
            n = self.rng.randint(cfg.min_bugs, cfg.max_bugs)
            wanted = self.rng.sample(range(len(CLASS_NAMES)), min(n, len(CLASS_NAMES)))
        else:
            wanted = []

        taken: list[Box] = []
        for class_id in wanted:
            placed = self._place_defect(image, class_id, taken)
            if placed is not None:
                box, annotation = placed
                taken.append(box)
                annotations.append(annotation)

        if wanted and not annotations:
            # Extremely unlikely, but never return a "buggy" scene without a bug.
            box, annotation = self._force_missing_texture(image)
            annotations.append(annotation)

        return SceneSample(
            image=image,
            annotations=annotations,
            has_bug=bool(annotations),
            clean_image=clean,
        )

    # ── scene ──────────────────────────────────────────────────

    def _draw_scene(self) -> np.ndarray:
        cfg = self.config
        h, w = cfg.height, cfg.width
        horizon = int(h * cfg.horizon_ratio)

        top = np.array([self.rng.randint(150, 235) for _ in range(3)], dtype=np.float32)
        bottom = np.array([self.rng.randint(150, 235) for _ in range(3)], dtype=np.float32)
        ramp = np.linspace(0.0, 1.0, horizon, dtype=np.float32)[:, None, None]
        sky = (top * (1 - ramp) + bottom * ramp).astype(np.uint8)
        image = np.empty((h, w, 3), dtype=np.uint8)
        image[:horizon] = sky
        ground = [self.rng.randint(50, 150) for _ in range(3)]
        image[horizon:] = ground
        cv2.line(image, (0, horizon), (w, horizon), (20, 20, 20), 1)

        for _ in range(self.rng.randint(cfg.min_buildings, cfg.max_buildings)):
            bw = self.rng.randint(32, 96)
            bh = self.rng.randint(60, int(horizon * 0.9))
            x1 = self.rng.randint(0, w - bw)
            body = tuple(self.rng.randint(60, 200) for _ in range(3))
            cap = tuple(min(255, max(0, c + self.rng.choice((-45, 45)))) for c in body)
            y1 = horizon - bh
            cv2.rectangle(image, (x1, y1), (x1 + bw, horizon), body, -1)
            cv2.rectangle(image, (x1, y1), (x1 + bw, y1 + 7), cap, -1)

        for _ in range(self.rng.randint(2, 5)):
            radius = self.rng.randint(6, 14)
            cx = self.rng.randint(radius, w - radius)
            cy = self.rng.randint(horizon + radius + 4, h - radius)
            colour = tuple(self.rng.randint(40, 200) for _ in range(3))
            cv2.circle(image, (cx, cy), radius, colour, -1)
        return image

    # ── placement ──────────────────────────────────────────────

    def _random_box(
        self,
        width_range: tuple[int, int],
        height_range: tuple[int, int],
        y_range: tuple[int, int] | None = None,
    ) -> Box:
        cfg = self.config
        w = min(self.rng.randint(*width_range), cfg.width)
        h = min(self.rng.randint(*height_range), cfg.height)
        x1 = self.rng.randint(0, cfg.width - w)
        low, high = (0, cfg.height - h) if y_range is None else y_range
        high = min(high, cfg.height - h)
        low = max(0, min(low, high))
        y1 = self.rng.randint(low, high)
        return x1, y1, x1 + w, y1 + h

    def _box_for(self, class_id: int) -> Box:
        cfg = self.config
        size = (cfg.min_defect_size, cfg.max_defect_size)
        if class_id == SCREEN_TEAR_CLASS_ID:
            horizon = int(cfg.height * cfg.horizon_ratio)
            return self._random_box(
                (int(cfg.width * 0.3), int(cfg.width * 0.75)),
                (44, 90),
                (horizon - 230, horizon - 50),
            )
        return self._random_box(size, size)

    @staticmethod
    def _overlaps(box: Box, others: Sequence[Box], margin: int = 6) -> bool:
        x1, y1, x2, y2 = box
        return any(
            x1 < ox2 + margin and x2 > ox1 - margin and y1 < oy2 + margin and y2 > oy1 - margin
            for ox1, oy1, ox2, oy2 in others
        )

    def _annotation(self, class_id: int, box: Box) -> Annotation:
        cfg = self.config
        x1, y1, x2, y2 = box
        return Annotation(
            class_id=class_id,
            cx=(x1 + x2) / 2 / cfg.width,
            cy=(y1 + y2) / 2 / cfg.height,
            w=(x2 - x1) / cfg.width,
            h=(y2 - y1) / cfg.height,
            is_bug=True,
        )

    def _place_defect(
        self, image: np.ndarray, class_id: int, taken: Sequence[Box]
    ) -> tuple[Box, Annotation] | None:
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
            change = float(np.abs(after.astype(np.int16) - before.astype(np.int16)).mean())
            if change < self.config.min_visibility:
                continue
            image[y1:y2, x1:x2] = after
            return box, self._annotation(class_id, box)
        return None

    def _force_missing_texture(self, image: np.ndarray) -> tuple[Box, Annotation]:
        cfg = self.config
        size = cfg.min_defect_size
        x1 = self.rng.randint(0, cfg.width - size)
        y1 = self.rng.randint(0, cfg.height - size)
        box = (x1, y1, x1 + size, y1 + size)
        image[y1 : y1 + size, x1 : x1 + size] = self._checker(
            size, size, 8, (255, 0, 255), (0, 0, 0)
        )
        return box, self._annotation(MISSING_TEXTURE_CLASS_ID, box)

    # ── defects: each returns the new patch, or None to reject the spot ──

    @staticmethod
    def _checker(h: int, w: int, cell: int, colour_a, colour_b) -> np.ndarray:
        yy, xx = np.indices((h, w))
        mask = ((yy // cell + xx // cell) % 2 == 0)[..., None]
        return np.where(mask, np.array(colour_a, np.uint8), np.array(colour_b, np.uint8))

    def _missing_texture(self, patch: np.ndarray, image: np.ndarray) -> np.ndarray | None:
        h, w = patch.shape[:2]
        cell = self.rng.choice((6, 8, 10, 12))
        colours = self.rng.choice(
            (
                ((255, 0, 255), (0, 0, 0)),
                ((200, 0, 200), (30, 30, 30)),
                ((255, 0, 255), (60, 60, 60)),
            )
        )
        return self._checker(h, w, cell, *colours)

    def _texture_glitch(self, patch: np.ndarray, image: np.ndarray) -> np.ndarray | None:
        h, w = patch.shape[:2]
        if self.rng.random() < 0.5:  # per-pixel noise
            noise = self.np_rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
            mix = self.rng.uniform(0.7, 1.0)
            return (noise * mix + patch * (1 - mix)).astype(np.uint8)
        block = self.rng.randint(4, 10)  # blocky compression-like artefacts
        small = self.np_rng.integers(0, 256, (h // block + 1, w // block + 1, 3), dtype=np.uint8)
        blocks = cv2.resize(small, (w + block, h + block), interpolation=cv2.INTER_NEAREST)
        return blocks[:h, :w]

    def _z_fighting(self, patch: np.ndarray, image: np.ndarray) -> np.ndarray | None:
        h, w = patch.shape[:2]
        colour_a, colour_b = self.rng.sample(_PALETTE, 2)
        stripe = self.rng.randint(2, 5)
        yy, xx = np.indices((h, w))
        axis = xx if self.rng.random() < 0.5 else yy
        mask = ((axis // stripe) % 2 == 0)[..., None]
        return np.where(mask, np.array(colour_a, np.uint8), np.array(colour_b, np.uint8))

    def _screen_tear(self, patch: np.ndarray, image: np.ndarray) -> np.ndarray | None:
        h, w = patch.shape[:2]
        tear_row = self.rng.randint(h // 3, 2 * h // 3)
        dx = self.rng.choice((-1, 1)) * self.rng.randint(14, 40)
        shifted = np.roll(patch[:tear_row], dx, axis=1)
        displacement = np.abs(shifted.astype(np.int16) - patch[:tear_row].astype(np.int16)).mean()
        if displacement < 8:  # flat area: the tear would not be visible
            return None
        out = patch.copy()
        out[:tear_row] = shifted
        out[max(0, tear_row - 1) : tear_row + 1] = (235, 235, 235)  # bright seam
        return out

    def _uv_stretch(self, patch: np.ndarray, image: np.ndarray) -> np.ndarray | None:
        h, w = patch.shape[:2]
        # Colours sampled from the scene itself, as if a tiny texture region
        # had been stretched over the whole surface.
        n = self.rng.randint(5, 12)
        ys = self.np_rng.integers(0, image.shape[0], n)
        xs = self.np_rng.integers(0, image.shape[1], n)
        strip = image[ys, xs].astype(np.uint8)[None, :, :]  # 1 x n x 3
        if self.rng.random() < 0.5:  # vertical streaks
            streaks = cv2.resize(strip, (w, h), interpolation=cv2.INTER_LINEAR)
        else:  # horizontal streaks
            streaks = cv2.resize(strip.transpose(1, 0, 2), (w, h), interpolation=cv2.INTER_LINEAR)
        return streaks

    def _color_corruption(self, patch: np.ndarray, image: np.ndarray) -> np.ndarray | None:
        h, w = patch.shape[:2]
        mode = self.rng.choice(("invert", "swap", "hue", "flat"))
        if mode == "invert":
            return 255 - patch
        if mode == "swap":
            order = self.rng.choice(((2, 0, 1), (1, 2, 0), (2, 1, 0)))
            return np.ascontiguousarray(patch[..., list(order)])
        if mode == "hue":
            hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).astype(np.int16)
            hsv[..., 0] = (hsv[..., 0] + self.rng.randint(60, 120)) % 180
            hsv[..., 1] = np.clip(hsv[..., 1] * 1.4 + 40, 0, 255)
            return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        colour = np.array(self.rng.choice(_WRONG_COLOURS), np.uint8)
        jitter = self.np_rng.integers(-6, 7, (h, w, 3))
        return np.clip(colour.astype(np.int16) + jitter, 0, 255).astype(np.uint8)
