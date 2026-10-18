"""Statistics computation for YOLO datasets."""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from .scanner import DatasetLayout
from .yolo_parser import parse_yolo_annotation, BoundingBox


@dataclass
class DatasetStats:
    """Aggregated statistics for a complete dataset."""
    total_images: int = 0
    total_labels: int = 0
    total_boxes: int = 0
    empty_labels: int = 0
    class_distribution: Dict[int, int] = field(default_factory=dict)
    images_per_split: Dict[str, int] = field(default_factory=dict)
    boxes_per_split: Dict[str, int] = field(default_factory=dict)
    image_widths: List[int] = field(default_factory=list)
    image_heights: List[int] = field(default_factory=list)
    bbox_areas: List[float] = field(default_factory=list)
    bbox_aspect_ratios: List[float] = field(default_factory=list)
    boxes_per_image: List[int] = field(default_factory=list)


def compute_statistics(
    layout: DatasetLayout,
    num_classes: int,
) -> DatasetStats:
    """Compute comprehensive statistics for a dataset.

    Args:
        layout: Discovered dataset layout.
        num_classes: Expected number of classes.

    Returns:
        DatasetStats with all computed statistics.
    """
    stats = DatasetStats()

    for split_name, split_layout in layout.splits.items():
        stats.images_per_split[split_name] = len(split_layout.image_files)
        stats.total_images += len(split_layout.image_files)
        stats.total_labels += len(split_layout.label_files)

        # Match labels to images
        label_stems = {p.stem: p for p in split_layout.label_files}

        for img in split_layout.image_files:
            stem = img.stem
            label_path = label_stems.get(stem)

            from PIL import Image
            try:
                with Image.open(img) as im:
                    stats.image_widths.append(im.width)
                    stats.image_heights.append(im.height)
            except Exception:
                continue

            if label_path is None:
                stats.boxes_per_image.append(0)
                continue

            ann = parse_yolo_annotation(label_path, num_classes)

            if not ann.boxes and not ann.errors:
                stats.empty_labels += 1

            stats.boxes_per_split[split_name] = \
                stats.boxes_per_split.get(split_name, 0) + len(ann.boxes)
            stats.total_boxes += len(ann.boxes)
            stats.boxes_per_image.append(len(ann.boxes))

            for box in ann.boxes:
                stats.class_distribution[box.class_id] = \
                    stats.class_distribution.get(box.class_id, 0) + 1
                stats.bbox_areas.append(box.area)
                if box.height > 0:
                    stats.bbox_aspect_ratios.append(box.width / box.height)

    return stats


def stats_summary(stats: DatasetStats, class_names: List[str] | None = None) -> str:
    """Generate a human-readable statistics summary.

    Args:
        stats: Computed DatasetStats.
        class_names: Optional list of class names for labels.

    Returns:
        Multi-line summary string.
    """
    lines = [
        "=" * 50,
        "Dataset Statistics Summary",
        "=" * 50,
        "",
        f"Total images:  {stats.total_images}",
        f"Total labels:  {stats.total_labels}",
        f"Total boxes:   {stats.total_boxes}",
        f"Empty labels:  {stats.empty_labels}",
        "",
        "Images per split:",
    ]
    for split, count in stats.images_per_split.items():
        lines.append(f"  {split}: {count}")

    lines.append("")
    lines.append("Boxes per split:")
    for split, count in stats.boxes_per_split.items():
        lines.append(f"  {split}: {count}")

    lines.append("")
    lines.append("Class distribution:")
    for cls_id in sorted(stats.class_distribution):
        label = class_names[cls_id] if class_names and cls_id < len(class_names) else f"class_{cls_id}"
        lines.append(f"  {label}: {stats.class_distribution[cls_id]}")

    if stats.image_widths:
        lines.append("")
        lines.append("Image sizes:")
        min_w, max_w = min(stats.image_widths), max(stats.image_widths)
        min_h, max_h = min(stats.image_heights), max(stats.image_heights)
        lines.append(f"  Width:  min={min_w}, max={max_w}")
        lines.append(f"  Height: min={min_h}, max={max_h}")
        # Count unique sizes
        size_counter = Counter(zip(stats.image_widths, stats.image_heights))
        lines.append(f"  Unique size combinations: {len(size_counter)}")
        for (w, h), cnt in size_counter.most_common(5):
            lines.append(f"    {w}x{h}: {cnt} images")

    if stats.bbox_areas:
        lines.append("")
        lines.append("Bounding box statistics:")
        areas = sorted(stats.bbox_areas)
        lines.append(f"  Area: min={min(areas):.4f}, max={max(areas):.4f}, "
                     f"median={areas[len(areas)//2]:.4f}")

    if stats.bbox_aspect_ratios:
        ratios = sorted(stats.bbox_aspect_ratios)
        lines.append(f"  Aspect ratio: min={min(ratios):.2f}, max={max(ratios):.2f}, "
                     f"median={ratios[len(ratios)//2]:.2f}")

    return "\n".join(lines)