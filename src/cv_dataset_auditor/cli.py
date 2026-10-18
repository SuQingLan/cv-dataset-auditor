"""Command-line interface for cv-dataset-auditor."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .scanner import discover_yolo_dataset
from .checker import audit_split, check_split_leakage, Finding
from .stats import compute_statistics, stats_summary, DatasetStats
from .reporter import generate_json_report, generate_html_report
from .visualizer import generate_annotation_gallery


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="YOLO dataset quality checker and annotation auditor."
    )
    parser.add_argument(
        "dataset_dir",
        type=str,
        help="Path to YOLO dataset directory.",
    )
    parser.add_argument(
        "-c", "--classes",
        type=int,
        required=True,
        help="Number of classes in the dataset.",
    )
    parser.add_argument(
        "--class-names",
        type=str,
        nargs="*",
        help="Optional class name labels (ordered by class ID).",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="audit-report",
        help="Output directory for reports (default: audit-report).",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip MD5 leakage check.",
    )
    parser.add_argument(
        "--no-visuals",
        action="store_true",
        help="Skip generating annotation gallery.",
    )
    parser.add_argument(
        "--max-visuals",
        type=int,
        default=30,
        help="Maximum preview images per split (default: 30).",
    )
    parser.add_argument(
        "--fail-on",
        choices=["error", "warning", "never"],
        default="error",
        help="Exit with code 1 if findings reach this level (default: error).",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Minimal output.",
    )
    parser.add_argument(
        "--gh-repo",
        type=str,
        default=None,
        help="owner/repo to submit the audit report issue to (GitHub API integration).",
    )
    parser.add_argument(
        "--gh-upload-report",
        action="store_true",
        default=False,
        help="Also upload report.json to the target repo (requires --gh-repo).",
    )
    parser.add_argument(
        "--gh-token",
        type=str,
        default=None,
        help="GitHub token. If omitted, reads GITHUB_TOKEN from the environment.",
    )

    opts = parser.parse_args(args)

    dataset_path = Path(opts.dataset_dir).resolve()
    if not dataset_path.is_dir():
        print(f"Error: '{dataset_path}' is not a valid directory.")
        return 2

    output_dir = Path(opts.output).resolve()

    if not opts.quiet:
        print(f"Auditing dataset: {dataset_path}")
        print(f"Classes: {opts.classes}")

    # Phase 1: Discover dataset layout
    layout = discover_yolo_dataset(str(dataset_path))

    if not layout.splits:
        print("Error: No dataset splits found. Expected YOLO directory structure.")
        return 2

    if not opts.quiet:
        print(f"Splits found: {', '.join(layout.splits.keys())}")

    # Phase 2: Audit each split
    all_findings: List[Finding] = []

    for split_name, split_layout in layout.splits.items():
        if not opts.quiet:
            print(f"\nAuditing {split_name} split ({len(split_layout.image_files)} images)...")
        result = audit_split(split_layout, opts.classes)
        all_findings.extend(result.findings)

        if not opts.quiet:
            img_errors = sum(1 for f in result.findings if f.severity == "error")
            img_warnings = sum(1 for f in result.findings if f.severity == "warning")
            print(f"  {split_name}: {img_errors} errors, {img_warnings} warnings")

    # Phase 3: Leakage check
    if not opts.no_hash:
        if not opts.quiet:
            print("\nChecking for split leakage...")
        leakage_findings = check_split_leakage(layout.splits)
        all_findings.extend(leakage_findings)
        if not opts.quiet:
            print(f"  Leakage findings: {len(leakage_findings)}")

    # Phase 4: Statistics
    stats = compute_statistics(layout, opts.classes)

    if not opts.quiet:
        print()
        print(stats_summary(stats, class_names=opts.class_names))

    # Phase 5: Visualizations
    if not opts.no_visuals:
        if not opts.quiet:
            print("\nGenerating annotation gallery...")
        for split_name, split_layout in layout.splits.items():
            gallery_dir = output_dir / "gallery" / split_name
            generated = generate_annotation_gallery(
                split_layout,
                opts.classes,
                gallery_dir,
                max_images=opts.max_visuals,
                class_names=opts.class_names,
            )
            if not opts.quiet:
                print(f"  {split_name}: {len(generated)} annotated images")

    # Phase 6: Reports
    generate_json_report(all_findings, stats, output_path=output_dir / "report.json")
    generate_html_report(all_findings, stats, class_names=opts.class_names,
                         output_path=output_dir / "report.html")

    if not opts.quiet:
        print(f"\nReports saved to: {output_dir}")

    # Phase 7: GitHub API integration (optional)
    if opts.gh_repo:
        from . import github_integration as gh
        token = opts.gh_token or gh.get_token()
        if not token:
            print("Error: --gh-repo requires a token via --gh-token or GITHUB_TOKEN env.")
            return 2
        report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
        try:
            issue = gh.submit_audit_issue(opts.gh_repo, report, token)
            if not opts.quiet:
                print(f"GitHub issue created: {issue.get('html_url', '')}")
        except gh.GitHubAPIError as e:
            print(f"GitHub issue creation failed: {e}")
            return 1

        if opts.gh_upload_report:
            try:
                stamp = datetime.now().strftime("%Y-%m-%d")
                content = (output_dir / "report.json").read_bytes()
                result = gh.upload_file(
                    opts.gh_repo,
                    f"reports/audit-{stamp}.json",
                    content,
                    token,
                )
                if not opts.quiet:
                    print(f"Report uploaded: {result.get('content', {}).get('html_url', '')}")
            except gh.GitHubAPIError as e:
                print(f"Report upload failed: {e}")
                return 1

    # Determine exit code
    has_errors = any(f.severity == "error" for f in all_findings)
    has_warnings = any(f.severity == "warning" for f in all_findings)

    if opts.fail_on == "error" and has_errors:
        return 1
    if opts.fail_on == "warning" and (has_errors or has_warnings):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())