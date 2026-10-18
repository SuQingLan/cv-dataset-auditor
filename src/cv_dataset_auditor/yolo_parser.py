"""YOLO annotation parser and validator."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class BoundingBox:
    """A single YOLO-format bounding box annotation.

    YOLO format: class_id center_x center_y width height (all normalized to [0,1]).
    """
    class_id: int
    center_x: float
    center_y: float
    width: float
    height: float

    @property
    def x1(self) -> float:
        return self.center_x - self.width / 2

    @property
    def y1(self) -> float:
        return self.center_y - self.height / 2

    @property
    def x2(self) -> float:
        return self.center_x + self.width / 2

    @property
    def y2(self) -> float:
        return self.center_y + self.height / 2

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass
class AnnotationFile:
    """Parsed YOLO annotation file."""
    path: Path
    boxes: List[BoundingBox] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    line_count: int = 0


def parse_yolo_annotation(file_path: Path, num_classes: int) -> AnnotationFile:
    """Parse a YOLO-format annotation file.

    Each line: class_id center_x center_y width height
    All values are space-separated, coordinates normalized to [0, 1].

    Empty files are treated as valid (no objects = background sample).

    Args:
        file_path: Path to the .txt annotation file.
        num_classes: Expected number of classes (class_id must be in [0, num_classes)).

    Returns:
        AnnotationFile with parsed boxes and any errors.
    """
    ann = AnnotationFile(path=file_path)

    if not file_path.exists():
        ann.errors.append("File not found")
        return ann

    try:
        content = file_path.read_text(encoding='utf-8').strip()
    except Exception as e:
        ann.errors.append(f"Cannot read file: {e}")
        return ann

    # Empty file = no objects (valid background sample)
    if not content:
        return ann

    for line_no, line in enumerate(content.split('\n'), 1):
        line = line.strip()
        if not line:
            continue
        ann.line_count += 1

        parts = line.split()
        if len(parts) < 5:
            ann.errors.append(f"Line {line_no}: expected 5 values, got {len(parts)}")
            continue

        try:
            values = [float(p) for p in parts[:5]]
        except ValueError as e:
            ann.errors.append(f"Line {line_no}: non-numeric value: {e}")
            continue

        class_id_raw, cx, cy, w, h = values

        # Validate class_id is integer
        if class_id_raw != int(class_id_raw):
            ann.errors.append(f"Line {line_no}: class_id must be integer, got {class_id_raw}")
            continue
        class_id = int(class_id_raw)

        # Validate class range
        if class_id < 0 or class_id >= num_classes:
            ann.errors.append(
                f"Line {line_no}: class_id {class_id} out of range [0, {num_classes})"
            )
            continue

        # Validate coordinate ranges (normalized [0, 1])
        coord_errors = []
        if not (0.0 <= cx <= 1.0):
            coord_errors.append(f"center_x={cx}")
        if not (0.0 <= cy <= 1.0):
            coord_errors.append(f"center_y={cy}")
        if w <= 0:
            coord_errors.append(f"width={w} (must be > 0)")
        elif not (0.0 <= w <= 1.0):
            coord_errors.append(f"width={w}")
        if h <= 0:
            coord_errors.append(f"height={h} (must be > 0)")
        elif not (0.0 <= h <= 1.0):
            coord_errors.append(f"height={h}")

        if coord_errors:
            ann.errors.append(f"Line {line_no}: invalid coordinates: {', '.join(coord_errors)}")
            continue

        # Check bounding box is within image bounds
        box = BoundingBox(class_id=class_id, center_x=cx, center_y=cy, width=w, height=h)
        if box.x1 < 0.0 or box.y1 < 0.0 or box.x2 > 1.0 or box.y2 > 1.0:
            ann.errors.append(
                f"Line {line_no}: bbox outside image bounds "
                f"({box.x1:.4f},{box.y1:.4f},{box.x2:.4f},{box.y2:.4f})"
            )
            continue

        ann.boxes.append(box)

    return ann