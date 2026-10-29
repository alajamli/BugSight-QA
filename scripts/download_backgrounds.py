"""Download real gameplay screenshots used as backgrounds for the semi-synthetic dataset.

Source: Hugging Face dataset ``Bingsu/Gameplay_Images`` (CC-BY-4.0), 10 games x
1000 screenshots at 640x360. Only an evenly spread sample per game is fetched
through the public datasets-server API, and each image is re-saved as JPEG.

Example:
    python scripts/download_backgrounds.py --per-game 200 --output data/backgrounds
"""

from __future__ import annotations

import argparse
import io
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

DATASET = "Bingsu/Gameplay_Images"
ROWS_URL = "https://datasets-server.huggingface.co/rows"
GAMES = [
    "Among Us",
    "Apex Legends",
    "Fortnite",
    "Forza Horizon",
    "Free Fire",
    "Genshin Impact",
    "God of War",
    "Minecraft",
    "Roblox",
    "Terraria",
]
PER_GAME_TOTAL = 1000  # rows are sorted by game, 1000 each
PAGE = 100  # datasets-server maximum page length


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _get(url: str, params: dict | None = None, retries: int = 4) -> requests.Response:
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=60)
            if resp.status_code == 200:
                return resp
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} {params or ''}")


def _rows(offset: int) -> list[dict]:
    params = {
        "dataset": DATASET,
        "config": "default",
        "split": "train",
        "offset": offset,
        "length": PAGE,
    }
    return _get(ROWS_URL, params).json()["rows"]


def _image_urls(pool: ThreadPoolExecutor, game_id: int, per_game: int) -> list[tuple[int, str]]:
    """(row index, signed image URL) for an evenly spread sample of one game."""
    step = max(1, PER_GAME_TOTAL // per_game)
    wanted = {game_id * PER_GAME_TOTAL + i * step for i in range(per_game)}
    first = game_id * PER_GAME_TOTAL
    offsets = [
        o for o in range(first, first + PER_GAME_TOTAL, PAGE) if wanted & set(range(o, o + PAGE))
    ]
    urls = []
    for rows in pool.map(_rows, offsets):
        for row in rows:
            if row["row_idx"] in wanted and row["row"]["label"] == game_id:
                urls.append((row["row_idx"], row["row"]["image"]["src"]))
    return urls


def _save(url: str, path: Path, quality: int) -> None:
    if path.exists():
        return
    image = Image.open(io.BytesIO(_get(url).content)).convert("RGB")
    image.save(path, "JPEG", quality=quality)


def download_backgrounds(output_dir: Path, per_game: int = 200, quality: int = 92) -> int:
    output_dir = Path(output_dir)
    total = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for game_id, game in enumerate(GAMES):
            game_dir = output_dir / _slug(game)
            game_dir.mkdir(parents=True, exist_ok=True)
            urls = _image_urls(pool, game_id, per_game)
            jobs = [
                pool.submit(_save, url, game_dir / f"{_slug(game)}_{idx:05d}.jpg", quality)
                for idx, url in urls
            ]
            for job in jobs:
                job.result()
            total += len(jobs)
            print(f"[backgrounds] {game:<15} {len(jobs)} images", flush=True)

    (output_dir / "ATTRIBUTION.md").write_text(
        "Gameplay screenshots from the Hugging Face dataset "
        f"[{DATASET}](https://huggingface.co/datasets/{DATASET}), licensed CC-BY-4.0.\n"
        "Used as backgrounds for the BugSight semi-synthetic dataset.\n",
        encoding="utf-8",
    )
    print(f"[backgrounds] {total} images in {output_dir}")
    return total


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download real gameplay screenshots.")
    p.add_argument("--output", type=Path, default=Path("data/backgrounds"))
    p.add_argument("--per-game", type=int, default=200)
    p.add_argument("--quality", type=int, default=92)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    download_backgrounds(args.output, per_game=args.per_game, quality=args.quality)


if __name__ == "__main__":
    main()
