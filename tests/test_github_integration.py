"""Tests for the GitHub API integration (no real network calls)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestGitHubIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _sample_report(self) -> dict:
        return {
            "audit_time": "2026-10-18T12:00:00+00:00",
            "summary": {
                "total_findings": 5,
                "errors": 3,
                "warnings": 2,
                "info": 0,
                "total_images": 13,
                "total_labels": 12,
                "total_boxes": 10,
            },
            "images_per_split": {"train": 8, "val": 3, "test": 2},
            "boxes_per_split": {"train": 5, "val": 4, "test": 1},
            "class_distribution": {0: 5, 1: 4, 2: 1},
            "findings": [
                {
                    "severity": "error",
                    "category": "leakage",
                    "split": "train & val",
                    "file": "demo/images/train/train_0.jpg",
                    "message": "Identical image found in both train and val splits",
                },
                {
                    "severity": "warning",
                    "category": "pairing",
                    "split": "train",
                    "file": "demo/images/train/no_label.jpg",
                    "message": "Missing label for no_label.jpg",
                },
            ],
        }

    def test_get_token_from_env(self):
        from cv_dataset_auditor.github_integration import get_token
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "abc123"}, clear=False):
            self.assertEqual(get_token(), "abc123")

    def test_get_token_missing_returns_none(self):
        from cv_dataset_auditor.github_integration import get_token
        with mock.patch.dict("os.environ", {}, clear=False):
            self.assertIsNone(get_token())

    def test_build_issue_body_contains_summary(self):
        from cv_dataset_auditor.github_integration import build_issue_body
        body = build_issue_body(self._sample_report())
        self.assertIn("图片总数", body)
        self.assertIn("13", body)
        self.assertIn("Error", body)
        self.assertIn("3", body)
        self.assertIn("leakage", body)
        self.assertIn("Identical image found", body)
        self.assertIn("cv-dataset-auditor", body)

    def test_issue_body_strips_absolute_paths(self):
        """Regression: public issue bodies must not leak local absolute paths."""
        from cv_dataset_auditor.github_integration import build_issue_body
        report = self._sample_report()
        # Inject a Windows-style absolute path
        report["findings"][0]["file"] = r"C:\Users\素质\secret\demo\train_0.jpg"
        body = build_issue_body(report)
        self.assertNotIn("C:\\", body)
        self.assertNotIn("Users", body)
        self.assertIn("train_0.jpg", body)

    def test_create_issue_makes_post_request(self):
        from cv_dataset_auditor import github_integration as gh

        captured = {}

        class FakeResp:
            def __init__(self, data):
                self._data = data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(self._data).encode("utf-8")

        def fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = json.loads(req.data.decode("utf-8")) if req.data else None
            captured["auth"] = req.get_header("Authorization")
            return FakeResp({"html_url": "https://github.com/x/y/issues/1", "number": 1})

        with mock.patch.object(gh.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = gh.create_issue("owner/repo", "Title", "Body", "tok123")

        self.assertEqual(captured["url"], "https://api.github.com/repos/owner/repo/issues")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["auth"], "Bearer tok123")
        self.assertEqual(captured["body"]["title"], "Title")
        self.assertEqual(captured["body"]["body"], "Body")
        self.assertEqual(result["html_url"], "https://github.com/x/y/issues/1")

    def test_create_issue_http_error(self):
        import io
        import urllib.error
        from cv_dataset_auditor.github_integration import GitHubAPIError, create_issue

        fp = io.BytesIO(b'{"message": "Resource not accessible"}')
        error = urllib.error.HTTPError(
            "https://api.github.com/repos/o/r/issues", 403, "Forbidden",
            {}, fp,
        )
        # HTTPError keeps the fp; make it closable so no resource warning leaks
        error.close = lambda: fp.close()  # noqa: B301

        with mock.patch.object(urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(GitHubAPIError) as ctx:
                create_issue("owner/repo", "t", "b", "tok")
        fp.close()
        self.assertIn("403", str(ctx.exception))
        self.assertIn("403", str(ctx.exception))

    def test_submit_audit_issue_title(self):
        from cv_dataset_auditor.github_integration import submit_audit_issue
        with mock.patch(
            "cv_dataset_auditor.github_integration.create_issue",
            return_value={"html_url": "https://example.com/i"},
        ) as m:
            submit_audit_issue("owner/repo", self._sample_report(), "tok")
        title = m.call_args[0][1]
        self.assertIn("13 images", title)
        self.assertIn("3 errors", title)
        self.assertIn("2 warnings", title)


if __name__ == "__main__":
    unittest.main()