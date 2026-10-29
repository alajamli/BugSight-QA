"""Pack the training code and one dataset into a zip to upload to Colab / Kaggle.

Example:
    python scripts/make_colab_bundle.py        # -> dist/bugsight_colab.zip

Upload the zip to Google Drive (MyDrive/) and run notebooks/train_colab.ipynb.
Only what training needs is packed: src/, scripts/, configs/ and the dataset
(without Ultralytics *.cache files, which hold local absolute paths).
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = ("src", "scripts", "configs")


def _files(folder: Path):
    for path in sorted(folder.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".cache":
            yield path


def make_bundle(dataset: Path, output: Path) -> Path:
    dataset = (ROOT / dataset).resolve()
    if not (dataset / "data.yaml").exists():
        raise FileNotFoundError(f"{dataset / 'data.yaml'} not found. Generate the dataset first.")
    output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as zf:  # images are already JPEG
        for folder in (*(ROOT / d for d in CODE_DIRS), dataset):
            for path in _files(folder):
                zf.write(path, path.relative_to(ROOT).as_posix())
                count += 1
    size_mb = output.stat().st_size / 1e6
    print(f"[colab_bundle] {count} files, {size_mb:.0f} MB -> {output}")
    return output


def split_bundle(bundle: Path, part_mb: float) -> list[Path]:
    """Cut the zip into ``<name>.partNN`` files for uploaders with a size limit.

    The notebook joins them back in name order.
    """
    for old in bundle.parent.glob(f"{bundle.name}.part*"):
        old.unlink()
    part_size = int(part_mb * 1024 * 1024)
    parts = []
    with open(bundle, "rb") as src:
        while chunk := src.read(part_size):
            part = bundle.with_name(f"{bundle.name}.part{len(parts):02d}")
            part.write_bytes(chunk)
            parts.append(part)
    print(f"[colab_bundle] split into {len(parts)} parts of <= {part_mb} MB")
    return parts


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Zip code + dataset for Colab training.")
    p.add_argument("--dataset", type=Path, default=Path("data/processed_semi"))
    p.add_argument("--output", type=Path, default=Path("dist/bugsight_colab.zip"))
    p.add_argument("--split-mb", type=float, default=None, help="also cut into parts of this size")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    bundle = make_bundle(args.dataset, args.output)
    if args.split_mb:
        split_bundle(bundle, args.split_mb)


if __name__ == "__main__":
    main()
