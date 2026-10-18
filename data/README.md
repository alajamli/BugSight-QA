# Data

This folder holds datasets and annotations. Contents are gitignored.

## Layout

    data/
    +-- raw/              # Original generated images
    +-- processed/        # Train/val/test splits (YOLO format)
    +-- annotations/      # Raw label files
    +-- dataset_card.yaml # Dataset metadata

## Generate the dataset

    python scripts/generate_dataset.py --n-images 2000 --output data/processed

This produces ~1400 train / 400 val / 200 test images in YOLO format.