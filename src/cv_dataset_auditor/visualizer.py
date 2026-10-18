"""Visualization: overlay YOLO annotations on images."""

import colorsys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .yolo_parser import parse_yolo_annotation, BoundingBox


# Predefined colors for up to 20 classes
_CLASS_COLORS: List[Tuple[int, int, int]] = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 0, 0), (0, 128, 0),
    (0, 0, 128), (128, 128, 0), (128, 0, 128), (0, 128, 128),
    (192, 64, 64), (64, 192, 64), (64, 64, 192), (192, 192, 64),
    (192, 64, 192), (64, 192, 192), (64, 64, 64), (192, 192, 192),
]


def get_color(class_id: int) -> Tuple[int, int, int]:
    """Get a consistent color for a class ID."""
    if class_id < len(_CLASS_COLORS):
        return _CLASS_COLORS[class_id]
    hue = (class_id * 0.618033988749895) % 1.0  # Golden ratio
    rgb = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
    return tuple(int(c * 255) for c in rgb)


def draw_boxes(
    image_path: Path,
    boxes: List[BoundingBox],
    class_names: Optional[List[str]] = None,
    line_width: int = 2,
) -> Image.Image:
    """Draw bounding boxes on an image.

    Args:
        image_path: Path to the source image.
        boxes: List of bounding boxes (normalized coordinates).
        class_names: Optional class name labels.
        line_width: Width of bounding box lines.

    Returns:
        PIL Image with overlaid annotations.
    """
    with Image.open(image_path) as src:
        img = src.convert('RGB').copy()

    draw = ImageDraw.Draw(img)
    w, h = img.size

    for box in boxes:
        x1 = int(box.x1 * w)
        y1 = int(box.y1 * h)
        x2 = int(box.x2 * w)
        y2 = int(box.y2 * h)

        color = get_color(box.class_id)

        # Draw rectangle
        for offset in range(line_width):
            draw.rectangle(
                (x1 + offset, y1 + offset, x2 - offset, y2 - offset),
                outline=color,
            )

        # Draw label
        label = class_names[box.class_id] if class_names and box.class_id < len(class_names) else str(box.class_id)
        draw.text((x1 + 2, y1 - 14), label, fill=color)

    return img


def generate_annotation_gallery(
    split_layout,
    num_classes: int,
    output_dir: Path,
    max_images: int = 30,
    class_names: Optional[List[str]] = None,
) -> List[Path]:
    """Generate annotated preview images for a dataset split.

    Args:
        split_layout: SplitLayout to visualize.
        num_classes: Expected number of classes.
        output_dir: Directory for output images.
        max_images: Maximum number of preview images to generate.
        class_names: Optional class name labels.

    Returns:
        List of paths to generated preview images.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: List[Path] = []

    label_stems = {p.stem: p for p in split_layout.label_files}

    for img_path in split_layout.image_files[:max_images]:
        stem = img_path.stem
        label_path = label_stems.get(stem)

        boxes: List[BoundingBox] = []
        if label_path:
            ann = parse_yolo_annotation(label_path, num_classes)
            boxes = ann.boxes

        try:
            annotated = draw_boxes(img_path, boxes, class_names=class_names)
            out_path = output_dir / f"{stem}_annotated.jpg"
            annotated.save(out_path, quality=85)
            generated.append(out_path)
        except Exception as e:
            print(f"  Warning: Cannot annotate {img_path.name}: {e}")

    return generated