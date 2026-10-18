"""Generate a synthetic YOLO dataset with intentional issues for testing."""

import shutil
from pathlib import Path

from PIL import Image, ImageDraw


def _make_image(path: Path, size=(320, 240), seed: int = 0):
    """Create a visually distinct image using a deterministic pseudo-random seed.

    Every call with a different seed produces a different byte stream,
    so MD5 hashes are unique unless a file is deliberately copied.
    """
    import random
    rng = random.Random(seed)
    w, h = size
    img = Image.new('RGB', size, (rng.randint(20, 235), rng.randint(20, 235), rng.randint(20, 235)))
    draw = ImageDraw.Draw(img)

    # Random background shapes so different seeds produce different pixels
    for _ in range(rng.randint(4, 10)):
        color = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        shape = rng.choice(['rect', 'ellipse', 'line'])
        x1, y1 = rng.randint(0, w - 1), rng.randint(0, h - 1)
        x2, y2 = rng.randint(0, w - 1), rng.randint(0, h - 1)
        if shape == 'rect':
            draw.rectangle((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)), fill=color)
        elif shape == 'ellipse':
            draw.ellipse((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)), outline=color)
        else:
            draw.line((x1, y1, x2, y2), fill=color, width=rng.randint(1, 8))

    # A structured object in the middle (approximating an annotation target)
    obj_x, obj_y = rng.randint(30, w - 80), rng.randint(30, h - 80)
    obj_w, obj_h = rng.randint(40, 100), rng.randint(30, 80)
    draw.rectangle((obj_x, obj_y, obj_x + obj_w, obj_y + obj_h), fill=(255, 60, 60))
    draw.rectangle((obj_x - 4, obj_y - 4, obj_x + obj_w + 4, obj_y + obj_h + 4),
                   outline=(20, 20, 20), width=2)

    img.save(path)


def generate_demo_dataset(output_dir: str, num_classes: int = 3) -> Path:
    """Create a minimal YOLO-format dataset with known issues.

    Creates:
    - train: 6 valid-ish images + 1 corrupt + 1 missing label + 1 orphan label + 1 bad-format label
    - val: 2 valid images + 1 leaked from train + 1 out-of-range class annotation
    - test: 2 valid images (one empty/background label)

    Issues intentionally introduced (all images unique by seed, except leaked.jpg):
    - train/corrupt.jpg: truncated image data
    - train/no_label.jpg: image without matching label file
    - train/train_5.txt: orphan label (no matching image)
    - train/bad_format.txt: invalid annotation format (has matching image)
    - val/leaked.jpg: byte-identical to train/train_0.jpg (split leakage)
    - val/val_2.txt: class_id out of range
    - test/test_1.txt: valid empty label (background)
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    class_names = ['cat', 'dog', 'bird'][:num_classes]

    def make_split(name: str):
        img_dir = root / 'images' / name
        lbl_dir = root / 'labels' / name
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        return img_dir, lbl_dir

    # ---- Train split ----
    train_img, train_lbl = make_split('train')

    # train_0: 2 objects (cat + dog) — ALSO the deliberate leak source
    _make_image(train_img / 'train_0.jpg', (320, 240), seed=10)
    (train_lbl / 'train_0.txt').write_text(
        "0 0.25 0.25 0.15 0.15\n1 0.75 0.75 0.20 0.20\n"
    )

    # train_1: 1 object (bird)
    _make_image(train_img / 'train_1.jpg', (640, 480), seed=11)
    (train_lbl / 'train_1.txt').write_text("2 0.50 0.50 0.30 0.40\n")

    # train_2: 1 object (cat near edge)
    _make_image(train_img / 'train_2.jpg', (320, 240), seed=12)
    (train_lbl / 'train_2.txt').write_text("0 0.10 0.10 0.15 0.20\n")

    # train_3: valid empty (background)
    _make_image(train_img / 'train_3.jpg', (320, 240), seed=13)
    (train_lbl / 'train_3.txt').write_text("")

    # train_4: valid single object
    _make_image(train_img / 'train_4.jpg', (640, 480), seed=14)
    (train_lbl / 'train_4.txt').write_text("1 0.50 0.50 0.20 0.20\n")

    # bad_format: image WITH label, label has invalid format
    _make_image(train_img / 'bad_format.jpg', (320, 240), seed=15)
    (train_lbl / 'bad_format.txt').write_text("invalid line\n0 0.5 0.5 0.2\n")

    # no_label: image without label
    _make_image(train_img / 'no_label.jpg', (320, 240), seed=16)

    # corrupt: truncated image (no label needed; image fails to open)
    (train_img / 'corrupt.jpg').write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 100)

    # train_5.txt: orphan label (no matching image)
    (train_lbl / 'train_5.txt').write_text("1 0.50 0.50 0.20 0.20\n")

    # ---- Val split ----
    val_img, val_lbl = make_split('val')

    # val_0: byte-identical leak of train_0.jpg (deliberate)
    shutil.copyfile(train_img / 'train_0.jpg', val_img / 'leaked.jpg')
    (val_lbl / 'leaked.txt').write_text(
        "0 0.25 0.25 0.15 0.15\n1 0.75 0.75 0.20 0.20\n"
    )

    # val_1: valid
    _make_image(val_img / 'val_1.jpg', (640, 480), seed=21)
    (val_lbl / 'val_1.txt').write_text("0 0.50 0.50 0.25 0.30\n")

    # val_2: out of range class_id
    _make_image(val_img / 'val_2.jpg', (320, 240), seed=22)
    (val_lbl / 'val_2.txt').write_text(
        f"0 0.30 0.30 0.20 0.20\n{num_classes} 0.70 0.70 0.20 0.20\n"
    )

    # ---- Test split ----
    test_img, test_lbl = make_split('test')

    _make_image(test_img / 'test_0.jpg', (320, 240), seed=31)
    (test_lbl / 'test_0.txt').write_text("1 0.50 0.50 0.30 0.30\n")

    _make_image(test_img / 'test_1.jpg', (640, 480), seed=32)
    (test_lbl / 'test_1.txt').write_text("")  # Empty = background

    # Write classes file
    (root / 'classes.txt').write_text('\n'.join(class_names))

    print(f"Generated demo dataset at: {root}")
    print(f"  Classes: {class_names}")
    print(f"  Train: {len(list((root/'images'/'train').iterdir()))} objects in images dir")
    print(f"  Val:   {len(list((root/'images'/'val').iterdir()))} objects in images dir")
    print(f"  Test:  {len(list((root/'images'/'test').iterdir()))} objects in images dir")
    print("\nIntentional issues:")
    print("  - corrupt.jpg: truncated image data")
    print("  - no_label.jpg: missing label file")
    print("  - train_5.txt: orphan label (no image)")
    print("  - bad_format.txt: invalid annotation format (with image)")
    print("  - leaked.jpg: byte-identical to train_0.jpg (split leakage)")
    print("  - val_2.txt: class_id out of range")
    print("  - test_1.txt: valid empty label (background)")
    return root


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "demo_dataset"
    classes = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    generate_demo_dataset(out, classes)