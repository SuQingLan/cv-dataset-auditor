"""Validation checks for YOLO datasets."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageFile

from .scanner import DatasetLayout, SplitLayout, match_pairs
from .yolo_parser import parse_yolo_annotation, AnnotationFile

ImageFile.LOAD_TRUNCATED_IMAGES = True


@dataclass
class Finding:
    """A single finding from a validation check."""
    severity: str  # "error", "warning", "info"
    category: str
    split: str
    file: str
    message: str


@dataclass
class AuditResult:
    """Complete audit results for a dataset."""
    findings: List[Finding] = field(default_factory=list)
    total_images: int = 0
    total_labels: int = 0
    total_boxes: int = 0
    class_distribution: Dict[int, int] = field(default_factory=dict)
    image_sizes: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    bbox_stats: Dict[str, List[float]] = field(default_factory=dict)


def audit_split(
    split: SplitLayout,
    num_classes: int,
) -> AuditResult:
    """Run all validation checks on a single dataset split.

    Args:
        split: The split to audit.
        num_classes: Expected number of classes.

    Returns:
        AuditResult with all findings.
    """
    result = AuditResult()
    pairs = match_pairs(split)
    result.total_images = len(split.image_files)
    result.total_labels = len(split.label_files)

    # Find orphan labels (labels without images)
    image_stems = {p.stem for p in split.image_files}
    for lbl in split.label_files:
        if lbl.stem not in image_stems:
            result.findings.append(Finding(
                severity="warning",
                category="pairing",
                split=split.name,
                file=str(lbl),
                message=f"Orphan label: no matching image for {lbl.name}",
            ))

    # Check each image
    for img in split.image_files:
        img_stem = img.stem
        label_path = pairs.get(img_stem)

        # Check image validity
        try:
            with Image.open(img) as im:
                im.verify()
            # Reopen to get size (verify() may close)
            with Image.open(img) as im:
                w, h = im.size
                if w <= 0 or h <= 0:
                    result.findings.append(Finding(
                        severity="error",
                        category="image",
                        split=split.name,
                        file=str(img),
                        message=f"Invalid image dimensions: {w}x{h}",
                    ))
                    continue
                result.image_sizes[str(img)] = (w, h)
        except Exception as e:
            result.findings.append(Finding(
                severity="error",
                category="image",
                split=split.name,
                file=str(img),
                message=f"Cannot open image: {e}",
            ))
            continue

        # Check label file
        if label_path is None:
            result.findings.append(Finding(
                severity="warning",
                category="pairing",
                split=split.name,
                file=str(img),
                message=f"Missing label for {img.name}",
            ))
            continue

        ann = parse_yolo_annotation(label_path, num_classes)
        for err in ann.errors:
            result.findings.append(Finding(
                severity="error",
                category="label",
                split=split.name,
                file=str(label_path),
                message=err,
            ))

        result.total_boxes += len(ann.boxes)
        for box in ann.boxes:
            result.class_distribution[box.class_id] = \
                result.class_distribution.get(box.class_id, 0) + 1
            result.bbox_stats.setdefault('areas', []).append(box.area)
            result.bbox_stats.setdefault('aspect_ratios', []).append(
                box.width / box.height if box.height > 0 else 0
            )

        # Check for empty boxes (no objects AND no errors = intentional background)
        # No warning needed for valid empty labels

    return result


def check_split_leakage(
    splits: Dict[str, SplitLayout],
    method: str = "md5",
) -> List[Finding]:
    """Detect images that appear in multiple splits (potential data leakage).

    Args:
        splits: Dict of split_name -> SplitLayout.
        method: "md5" for byte-exact comparison.

    Returns:
        List of Findings for leaked images.
    """
    findings: List[Finding] = []
    split_hashes: Dict[str, Dict[str, List[Path]]] = {}

    import hashlib

    for split_name, split_layout in splits.items():
        hashes: Dict[str, List[Path]] = {}
        for img in split_layout.image_files:
            try:
                with open(img, 'rb') as f:
                    h = hashlib.file_digest(f, 'md5').hexdigest()
                hashes.setdefault(h, []).append(img)
            except Exception:
                continue
        split_hashes[split_name] = hashes

    # Cross-reference all split pairs
    split_names = list(split_hashes.keys())
    for i in range(len(split_names)):
        for j in range(i + 1, len(split_names)):
            name_a, name_b = split_names[i], split_names[j]
            common = set(split_hashes[name_a]) & set(split_hashes[name_b])
            for h in common:
                findings.append(Finding(
                    severity="error",
                    category="leakage",
                    split=f"{name_a} & {name_b}",
                    file=str(split_hashes[name_a][h][0]),
                    message=f"Identical image found in both {name_a} and {name_b} splits",
                ))

    return findings