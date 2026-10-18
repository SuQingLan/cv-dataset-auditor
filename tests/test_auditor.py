"""Tests for cv-dataset-auditor: YOLO dataset quality checker."""

import hashlib
import shutil
import tempfile
from pathlib import Path
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


class TestYoloParser(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_annotation(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'labels.txt'
        label_file.write_text("0 0.5 0.5 0.2 0.2\n1 0.8 0.8 0.1 0.1\n")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 2)
        self.assertEqual(ann.boxes[0].class_id, 0)
        self.assertEqual(ann.boxes[1].class_id, 1)
        self.assertEqual(len(ann.errors), 0)

    def test_empty_label_is_valid(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'empty.txt'
        label_file.write_text("")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 0)
        self.assertEqual(len(ann.errors), 0)

    def test_class_id_out_of_range(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'bad.txt'
        label_file.write_text("3 0.5 0.5 0.2 0.2\n")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 0)
        self.assertTrue(any('out of range' in e for e in ann.errors))

    def test_negative_class_id(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'neg.txt'
        label_file.write_text("-1 0.5 0.5 0.2 0.2\n")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 0)
        self.assertTrue(any('out of range' in e for e in ann.errors))

    def test_invalid_format(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'bad.txt'
        label_file.write_text("not numbers\n")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 0)
        self.assertTrue(any('expected 5 values' in e for e in ann.errors))

    def test_too_few_columns(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'few.txt'
        label_file.write_text("0 0.5 0.5\n")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertTrue(any('expected 5 values' in e for e in ann.errors))

    def test_coordinate_out_of_bounds(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'oob.txt'
        label_file.write_text("0 1.5 0.5 0.2 0.2\n")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 0)
        self.assertTrue(any('invalid coordinates' in e for e in ann.errors))

    def test_bbox_outside_image(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'outside.txt'
        # center at (0.95, 0.5) with width 0.3 means x2 = 1.1 > 1.0
        label_file.write_text("0 0.95 0.5 0.3 0.2\n")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 0)
        self.assertTrue(any('outside image bounds' in e for e in ann.errors))

    def test_zero_width_height(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'zero.txt'
        label_file.write_text("0 0.5 0.5 0.0 0.2\n")
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 0)
        self.assertTrue(any('must be > 0' in e for e in ann.errors))

    def test_mixed_valid_and_invalid(self):
        from cv_dataset_auditor.yolo_parser import parse_yolo_annotation
        label_file = self.root / 'mixed.txt'
        label_file.write_text(
            "0 0.5 0.5 0.2 0.2\n"
            "bad line\n"
            "1 0.8 0.8 0.1 0.1\n"
        )
        ann = parse_yolo_annotation(label_file, num_classes=3)
        self.assertEqual(len(ann.boxes), 2)
        self.assertEqual(len(ann.errors), 1)


class TestScanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_dataset(self):
        """Create a minimal valid YOLO dataset."""
        for split in ['train', 'val']:
            img_dir = self.root / 'images' / split
            lbl_dir = self.root / 'labels' / split
            img_dir.mkdir(parents=True)
            lbl_dir.mkdir(parents=True)
            from PIL import Image
            img = Image.new('RGB', (64, 64), 'red')
            img.save(img_dir / f'{split}_0.jpg')
            (lbl_dir / f'{split}_0.txt').write_text("0 0.5 0.5 0.2 0.2\n")

    def test_discover_ultralytics_layout(self):
        self._create_dataset()
        from cv_dataset_auditor.scanner import discover_yolo_dataset
        layout = discover_yolo_dataset(str(self.root))
        self.assertIn('train', layout.splits)
        self.assertIn('val', layout.splits)
        self.assertEqual(len(layout.splits['train'].image_files), 1)
        self.assertEqual(len(layout.splits['train'].label_files), 1)

    def test_match_pairs(self):
        self._create_dataset()
        from cv_dataset_auditor.scanner import discover_yolo_dataset, match_pairs
        layout = discover_yolo_dataset(str(self.root))
        pairs = match_pairs(layout.splits['train'])
        self.assertIsNotNone(pairs.get('train_0'))

    def test_empty_dataset(self):
        from cv_dataset_auditor.scanner import discover_yolo_dataset
        layout = discover_yolo_dataset(str(self.root))
        self.assertEqual(len(layout.splits), 0)


class TestChecker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_split(self, name, with_label=True):
        img_dir = self.root / 'images' / name
        lbl_dir = self.root / 'labels' / name
        img_dir.mkdir(parents=True)
        lbl_dir.mkdir(parents=True)
        from PIL import Image
        Image.new('RGB', (64, 64), 'red').save(img_dir / f'{name}_0.jpg')
        if with_label:
            (lbl_dir / f'{name}_0.txt').write_text("0 0.5 0.5 0.2 0.2\n")
        return img_dir, lbl_dir

    def test_audit_valid_split(self):
        self._make_split('train')
        from cv_dataset_auditor.scanner import discover_yolo_dataset
        from cv_dataset_auditor.checker import audit_split
        layout = discover_yolo_dataset(str(self.root))
        result = audit_split(layout.splits['train'], num_classes=3)
        self.assertEqual(result.total_images, 1)
        self.assertEqual(result.total_boxes, 1)

    def test_corrupt_image_detected(self):
        img_dir, lbl_dir = self._make_split('train')
        (img_dir / 'broken.jpg').write_bytes(b'not an image')
        from cv_dataset_auditor.scanner import discover_yolo_dataset
        from cv_dataset_auditor.checker import audit_split
        layout = discover_yolo_dataset(str(self.root))
        result = audit_split(layout.splits['train'], num_classes=3)
        self.assertTrue(any('Cannot open image' in f.message for f in result.findings))

    def test_missing_label_detected(self):
        self._make_split('train', with_label=False)
        from cv_dataset_auditor.scanner import discover_yolo_dataset
        from cv_dataset_auditor.checker import audit_split
        layout = discover_yolo_dataset(str(self.root))
        result = audit_split(layout.splits['train'], num_classes=3)
        self.assertTrue(any('Missing label' in f.message for f in result.findings))

    def test_orphan_label_detected(self):
        img_dir, lbl_dir = self._make_split('train', with_label=True)
        # Add an orphan label: keep the image, but add label without matching image
        (lbl_dir / 'orphan.txt').write_text("0 0.5 0.5 0.2 0.2\n")
        from cv_dataset_auditor.scanner import discover_yolo_dataset
        from cv_dataset_auditor.checker import audit_split
        layout = discover_yolo_dataset(str(self.root))
        result = audit_split(layout.splits['train'], num_classes=3)
        self.assertTrue(any('Orphan label' in f.message for f in result.findings),
                        [f.message for f in result.findings])

    def test_leakage_detection(self):
        self._make_split('train', with_label=True)
        self._make_split('val', with_label=True)
        # Make val image identical to train
        shutil.copyfile(
            self.root / 'images' / 'train' / 'train_0.jpg',
            self.root / 'images' / 'val' / 'leaked.jpg',
        )
        from cv_dataset_auditor.scanner import discover_yolo_dataset
        from cv_dataset_auditor.checker import check_split_leakage
        layout = discover_yolo_dataset(str(self.root))
        findings = check_split_leakage(layout.splits)
        self.assertTrue(any('both train and val' in f.message for f in findings),
                        [f.message for f in findings])


class TestDemoDataset(unittest.TestCase):
    """End-to-end test using the generated demo dataset."""

    def test_demo_dataset_audit(self):
        from PIL import Image, ImageDraw
        # Quick inline generation
        root = Path(tempfile.mkdtemp())
        try:
            colors = {'train': 'red', 'val': 'blue'}
            for split in ['train', 'val']:
                img_dir = root / 'images' / split
                lbl_dir = root / 'labels' / split
                img_dir.mkdir(parents=True)
                lbl_dir.mkdir(parents=True)
                Image.new('RGB', (64, 64), colors[split]).save(img_dir / f'{split}_a.jpg')
                (lbl_dir / f'{split}_a.txt').write_text("0 0.5 0.5 0.2 0.2\n")

            from cv_dataset_auditor.scanner import discover_yolo_dataset
            from cv_dataset_auditor.checker import audit_split, check_split_leakage
            from cv_dataset_auditor.stats import compute_statistics

            layout = discover_yolo_dataset(str(root))
            self.assertEqual(len(layout.splits), 2)

            findings = []
            for split_layout in layout.splits.values():
                result = audit_split(split_layout, num_classes=3)
                findings.extend(result.findings)

            leakage = check_split_leakage(layout.splits)
            findings.extend(leakage)

            stats = compute_statistics(layout, num_classes=3)
            self.assertEqual(stats.total_images, 2)
            self.assertEqual(stats.total_boxes, 2)

            # No findings expected for clean dataset
            errors = [f for f in findings if f.severity == 'error']
            warnings = [f for f in findings if f.severity == 'warning']
            self.assertEqual(len(errors), 0, [f.message for f in errors])
            self.assertEqual(len(warnings), 0, [f.message for f in warnings])
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()