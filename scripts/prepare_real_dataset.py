"""Prepare a real-image dataset for YOLO training.

Takes images + labels from data/real_dataset/ and creates train/val/test
splits in YOLO format at data/processed/.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

CLASS_NAMES = ["floating_object", "missing_texture", "clipping", "z_fighting"]


def prepare_real_dataset(
    source_dir: Path,
    output_dir: Path,
    val_size: float = 0.2,
    test_size: float = 0.1,
    seed: int = 42,
) -> None:
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)

    images = sorted(
        list((source_dir / "images").glob("*.jpg"))
        + list((source_dir / "images").glob("*.png"))
        + list((source_dir / "images").glob("*.jpeg"))
    )
    if not images:
        print(f"No images found in {source_dir / 'images'}")
        return

    print(f"Found {len(images)} images")

    try:
        from sklearn.model_selection import train_test_split
    except ImportError:
        print("Installing scikit-learn...")
        import subprocess

        subprocess.check_call(["pip", "install", "scikit-learn"])
        from sklearn.model_selection import train_test_split

    train_imgs, temp_imgs = train_test_split(
        images, test_size=val_size + test_size, random_state=seed
    )
    val_imgs, test_imgs = train_test_split(
        temp_imgs, test_size=test_size / (val_size + test_size), random_state=seed
    )

    splits = {"train": train_imgs, "val": val_imgs, "test": test_imgs}

    if output_dir.exists():
        shutil.rmtree(output_dir)

    for split, imgs in splits.items():
        img_dir = output_dir / "images" / split
        lbl_dir = output_dir / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        for img in imgs:
            shutil.copy2(img, img_dir / img.name)
            label = source_dir / "labels" / (img.stem + ".txt")
            if label.exists():
                shutil.copy2(label, lbl_dir / (img.stem + ".txt"))
            else:
                (lbl_dir / (img.stem + ".txt")).write_text("")

    yaml_content = f"""# BugSight QA - real dataset
path: {output_dir.resolve()}
train: images/train
val: images/val
test: images/test

nc: {len(CLASS_NAMES)}
names: {CLASS_NAMES}
"""
    (output_dir / "data.yaml").write_text(yaml_content)

    print(f"\nDataset prepared at {output_dir}")
    print(f"  train: {len(train_imgs)}")
    print(f"  val: {len(val_imgs)}")
    print(f"  test: {len(test_imgs)}")
    print("  data.yaml written")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/real_dataset"))
    parser.add_argument("--output", type=Path, default=Path("data/processed"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    prepare_real_dataset(args.source, args.output, seed=args.seed)
