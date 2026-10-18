"""Synthetic scene generator for multi-class bug detection.

Detects 4 bug types:
- floating_object (objet flottant dans les airs)
- missing_texture (texture vioire/noir damier)
- clipping (objet enfoncé dans le sol)
- z_fighting (deux objets superposés)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

FLOATING_OBJECT_CLASS_ID = 0
MISSING_TEXTURE_CLASS_ID = 1
CLIPPING_CLASS_ID = 2
Z_FIGHTING_CLASS_ID = 3
CLASS_NAMES = ["floating_object", "missing_texture", "clipping", "z_fighting"]


@dataclass
class SceneConfig:
    width: int = 640
    height: int = 480
    ground_ratio: float = 0.45
    bug_probability: float = 0.5
    min_objects: int = 2
    max_objects: int = 6
    min_object_size: int = 28
    max_object_size: int = 72
    allow_hard_negatives: bool = True
    seed: int | None = None

    sky_colors: tuple[tuple[int, int, int], ...] = (
        (220, 180, 120),
        (180, 170, 230),
        (190, 200, 250),
    )
    ground_colors: tuple[tuple[int, int, int], ...] = (
        (90, 140, 70),
        (110, 110, 60),
        (80, 100, 120),
    )
    object_colors: tuple[tuple[int, int, int], ...] = (
        (0, 0, 200),
        (0, 180, 60),
        (200, 160, 40),
        (40, 40, 40),
        (200, 200, 200),
    )

    def __post_init__(self) -> None:
        pass


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

    def save(self, image_path: Path, label_path: Path) -> None:
        image_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(image_path), self.image)
        lines = [a.to_yolo_line() for a in self.annotations if a.is_bug]
        label_path.write_text("\n".join(lines) + ("\n" if lines else ""))


class SceneGenerator:
    """Generate synthetic game scenes with multiple bug types."""

    def __init__(self, config: SceneConfig | None = None) -> None:
        self.config = config or SceneConfig()

    def generate(self) -> SceneSample:
        if self.config.seed is not None:
            random.seed(self.config.seed)
            np.random.seed(self.config.seed)
        cfg = self.config
        ground_y = int(cfg.height * cfg.ground_ratio)
        image = self._draw_background(ground_y)
        annotations = []
        has_bug = random.random() < cfg.bug_probability

        n_objects = random.randint(cfg.min_objects, cfg.max_objects)
        n_bugs = 0
        if has_bug:
            n_bugs = random.randint(1, max(1, n_objects // 2))

        for _ in range(n_objects - n_bugs):
            ann = self._place_object(image, ground_y, floating=False)
            annotations.append(ann)

        for _ in range(n_bugs):
            bug_type = random.choice(["floating", "texture", "clipping", "zfight"])
            if bug_type == "floating":
                ann = self._place_object(image, ground_y, floating=True)
            elif bug_type == "texture":
                ann = self._place_missing_texture(image, ground_y)
            elif bug_type == "clipping":
                ann = self._place_clipping(image, ground_y)
            else:
                ann = self._place_z_fighting(image, ground_y)
            annotations.append(ann)

        return SceneSample(image=image, annotations=annotations, has_bug=has_bug)

    def _draw_background(self, ground_y: int) -> np.ndarray:
        cfg = self.config
        image = np.zeros((cfg.height, cfg.width, 3), dtype=np.uint8)
        sky_color = random.choice(cfg.sky_colors)
        ground_color = random.choice(cfg.ground_colors)
        image[:ground_y] = sky_color
        image[ground_y:] = ground_color
        noise = np.random.randint(-12, 12, image.shape, dtype=np.int16)
        image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        cv2.line(image, (0, ground_y), (cfg.width, ground_y), (60, 60, 60), 1)
        return image

    def _make_bbox(self, x1, y1, size, w, h, class_id) -> Annotation:
        cx = (x1 + x1 + size) / 2 / w
        cy = (y1 + y1 + size) / 2 / h
        return Annotation(
            class_id=class_id,
            cx=cx,
            cy=cy,
            w=size / w,
            h=size / h,
            is_bug=True,
        )

    def _place_object(self, image, ground_y, *, floating):
        cfg = self.config
        h, w = image.shape[:2]
        size = random.randint(cfg.min_object_size, cfg.max_object_size)
        color = random.choice(cfg.object_colors)

        if floating:
            if cfg.allow_hard_negatives and random.random() < 0.25:
                top = ground_y - size - random.randint(2, 6)
            else:
                top = random.randint(20, max(21, ground_y - size - 10))
        else:
            top = ground_y + random.randint(0, max(0, h - ground_y - size))

        left = random.randint(0, w - size)
        x1, y1 = left, top
        x2, y2 = left + size, top + size

        cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)
        lighter = tuple(min(255, c + 40) for c in color)
        darker = tuple(max(0, c - 40) for c in color)
        cv2.rectangle(image, (x1, y1), (x2, y1 + max(3, (y2 - y1) // 6)), lighter, -1)
        cv2.rectangle(image, (x1, y2 - max(3, (y2 - y1) // 6)), (x2, y2), darker, -1)
        cv2.rectangle(image, (x1, y1), (x2, y2), darker, 1)

        if floating:
            ground_y_val = int(image.shape[0] * 0.45)
            shadow_y = ground_y_val + random.randint(2, 8)
            shadow_w = int((x2 - x1) * 0.8)
            shadow_x1 = (x1 + x2) // 2 - shadow_w // 2
            cv2.ellipse(
                image,
                ((shadow_x1 + shadow_w // 2), shadow_y),
                (shadow_w // 2, 5),
                0,
                0,
                360,
                (40, 40, 40),
                -1,
            )

        return self._make_bbox(x1, y1, size, w, h, FLOATING_OBJECT_CLASS_ID)

    def _place_missing_texture(self, image, ground_y):
        cfg = self.config
        h, w = image.shape[:2]
        size = random.randint(cfg.min_object_size, cfg.max_object_size)
        top = ground_y + random.randint(0, max(0, h - ground_y - size))
        left = random.randint(0, w - size)
        x1, y1 = left, top

        # Texture manquante : violet magenta + damier noir
        cv2.rectangle(image, (x1, y1), (x1 + size, y1 + size), (200, 0, 200), -1)
        for i in range(0, size, 8):
            for j in range(0, size, 8):
                if (i // 8 + j // 8) % 2 == 0:
                    cv2.rectangle(image, (x1 + i, y1 + j), (x1 + i + 8, y1 + j + 8), (0, 0, 0), -1)

        return self._make_bbox(x1, y1, size, w, h, MISSING_TEXTURE_CLASS_ID)

    def _place_clipping(self, image, ground_y):
        cfg = self.config
        h, w = image.shape[:2]
        size = random.randint(cfg.min_object_size, cfg.max_object_size)
        color = random.choice(cfg.object_colors)

        # Objet enfoncé dans le sol
        offset = random.randint(size // 4, size // 2)
        top = ground_y - offset
        left = random.randint(0, w - size)
        x1, y1 = left, top

        visible_bottom = min(y1 + size, ground_y)
        if visible_bottom > y1:
            cv2.rectangle(image, (x1, y1), (x1 + size, visible_bottom), color, -1)
            darker = tuple(max(0, c - 40) for c in color)
            cv2.rectangle(image, (x1, y1), (x1 + size, visible_bottom), darker, 1)

        return self._make_bbox(x1, y1, size, w, h, CLIPPING_CLASS_ID)

    def _place_z_fighting(self, image, ground_y):
        cfg = self.config
        h, w = image.shape[:2]
        size = random.randint(cfg.min_object_size, cfg.max_object_size)

        # Deux objets au même endroit avec couleurs différentes
        color1 = random.choice(cfg.object_colors)
        color2 = random.choice(cfg.object_colors)
        while color2 == color1:
            color2 = random.choice(cfg.object_colors)

        top = ground_y + random.randint(0, max(0, h - ground_y - size))
        left = random.randint(0, w - size)
        x1, y1 = left, top

        # Dessine des bandes alternées (effet z-fighting)
        stripe = 4
        for i in range(0, size, stripe):
            c = color1 if (i // stripe) % 2 == 0 else color2
            cv2.rectangle(image, (x1 + i, y1), (x1 + i + stripe, y1 + size), c, -1)
        cv2.rectangle(image, (x1, y1), (x1 + size, y1 + size), (0, 0, 0), 1)

        return self._make_bbox(x1, y1, size, w, h, Z_FIGHTING_CLASS_ID)
