"""Dataset structure scanner: discover and validate YOLO dataset layout."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}


@dataclass
class DatasetLayout:
    """Represents a YOLO-format dataset layout."""
    root: Path
    yaml_path: Optional[Path] = None
    splits: Dict[str, 'SplitLayout'] = field(default_factory=dict)


@dataclass
class SplitLayout:
    """A single split (train/val/test) in the dataset."""
    name: str
    image_dir: Path
    label_dir: Path
    image_files: List[Path] = field(default_factory=list)
    label_files: List[Path] = field(default_factory=list)


def discover_yolo_dataset(
    root: str,
    yaml_path: Optional[str] = None,
) -> DatasetLayout:
    """Discover YOLO dataset layout from a directory.

    Supports two layouts:
    1. Ultralytics-style: dataset.yaml pointing to images/ and labels/ with subdirs
    2. Split-first: train/images, train/labels, val/images, val/labels

    Args:
        root: Dataset root directory.
        yaml_path: Optional path to dataset.yaml.

    Returns:
        DatasetLayout with discovered splits.
    """
    root_path = Path(root).resolve()
    layout = DatasetLayout(root=root_path)

    # Try to read dataset.yaml
    if yaml_path:
        yaml_file = Path(yaml_path).resolve()
    else:
        yaml_file = root_path / 'data.yaml'
        if not yaml_file.exists():
            yaml_file = root_path / 'dataset.yaml'

    if yaml_file.exists():
        layout.yaml_path = yaml_file

    # Discover splits by scanning directory structure
    for split_name in ['train', 'val', 'test']:
        split_layout = _discover_split(root_path, split_name)
        if split_layout and split_layout.image_files:
            layout.splits[split_name] = split_layout

    return layout


def _discover_split(root: Path, split_name: str) -> Optional[SplitLayout]:
    """Try to discover a single split using common YOLO layouts."""
    # Layout 1: Ultralytics-style (images/train, labels/train)
    image_dir = root / 'images' / split_name
    label_dir = root / 'labels' / split_name

    if image_dir.is_dir():
        images = sorted(
            p for p in image_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        labels = sorted(
            p for p in label_dir.iterdir()
            if p.is_file() and p.suffix.lower() == '.txt'
        ) if label_dir.is_dir() else []

        return SplitLayout(
            name=split_name,
            image_dir=image_dir,
            label_dir=label_dir,
            image_files=images,
            label_files=labels,
        )

    # Layout 2: Split-first (train/images, train/labels)
    split_dir = root / split_name
    if split_dir.is_dir():
        img_dir = split_dir / 'images'
        lbl_dir = split_dir / 'labels'

        if img_dir.is_dir():
            images = sorted(
                p for p in img_dir.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
            )
            labels = sorted(
                p for p in lbl_dir.iterdir()
                if p.is_file() and p.suffix.lower() == '.txt'
            ) if lbl_dir.is_dir() else []

            return SplitLayout(
                name=split_name,
                image_dir=img_dir,
                label_dir=lbl_dir,
                image_files=images,
                label_files=labels,
            )

    return None


def match_pairs(split: SplitLayout) -> Dict[str, Optional[Path]]:
    """Match image files to label files by stem (filename without extension).

    Returns:
        Dict mapping image stem -> label path (or None if missing).
    """
    label_stems = {p.stem: p for p in split.label_files}
    pairs: Dict[str, Optional[Path]] = {}

    for img in split.image_files:
        pairs[img.stem] = label_stems.get(img.stem)

    return pairs