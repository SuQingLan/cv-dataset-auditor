"""HTML and JSON report generation for audit results."""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .checker import Finding, AuditResult
from .stats import DatasetStats, stats_summary


def generate_json_report(
    findings: List[Finding],
    stats: DatasetStats,
    output_path: Optional[Path] = None,
) -> Dict:
    """Generate a JSON audit report.

    Args:
        findings: All validation findings.
        stats: Computed statistics.
        output_path: Optional output file path.

    Returns:
        Report as a dict.
    """
    report = {
        "audit_time": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_findings": len(findings),
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "info": sum(1 for f in findings if f.severity == "info"),
            "total_images": stats.total_images,
            "total_labels": stats.total_labels,
            "total_boxes": stats.total_boxes,
        },
        "images_per_split": stats.images_per_split,
        "boxes_per_split": stats.boxes_per_split,
        "class_distribution": stats.class_distribution,
        "findings": [
            {
                "severity": f.severity,
                "category": f.category,
                "split": f.split,
                "file": f.file,
                "message": f.message,
            }
            for f in findings
        ],
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)

    return report


def generate_html_report(
    findings: List[Finding],
    stats: DatasetStats,
    class_names: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
) -> str:
    """Generate a self-contained HTML audit report.

    Args:
        findings: All validation findings.
        stats: Computed statistics.
        class_names: Optional class name labels for distribution.
        output_path: Optional output file path.

    Returns:
        HTML string.
    """
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos = [f for f in findings if f.severity == "info"]

    def _finding_rows(items: List[Finding]) -> str:
        rows = []
        for f in items:
            rows.append(
                f'<tr class="{f.severity}">'
                f'<td>{f.severity.upper()}</td>'
                f'<td>{f.category}</td>'
                f'<td>{f.split}</td>'
                f'<td class="file">{f.file}</td>'
                f'<td>{f.message}</td>'
                f'</tr>'
            )
        return "\n".join(rows)

    # Class distribution table
    class_rows = []
    for cls_id in sorted(stats.class_distribution):
        label = class_names[cls_id] if class_names and cls_id < len(class_names) else f"class_{cls_id}"
        class_rows.append(
            f'<tr><td>{cls_id}</td><td>{label}</td>'
            f'<td>{stats.class_distribution[cls_id]}</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>CV Dataset Audit Report</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1100px; margin: 0 auto; padding: 24px; color: #333; }}
.summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}
.card {{ background: #f8f9fa; border-radius: 8px; padding: 14px; min-width: 120px; text-align: center; }}
.card .label {{ font-size: 0.8em; color: #666; }}
.card .value {{ font-size: 1.6em; font-weight: bold; }}
.card.error .value {{ color: #d32f2f; }}
.card.warning .value {{ color: #f57c00; }}
h2 {{ border-bottom: 2px solid #eee; padding-bottom: 8px; margin-top: 32px; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #eee; font-size: 0.9em; }}
th {{ background: #f5f5f5; font-weight: 600; }}
tr.error {{ background: #fff5f5; }}
tr.warning {{ background: #fffde7; }}
tr.info {{ background: #f5f5ff; }}
.file {{ font-family: monospace; font-size: 0.85em; word-break: break-all; }}
.filter-bar {{ margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; }}
.filter-bar button {{ padding: 6px 14px; border: 1px solid #ccc; border-radius: 4px; background: #fff; cursor: pointer; }}
.filter-bar button.active {{ background: #1976d2; color: #fff; border-color: #1976d2; }}
</style>
</head>
<body>
<h1>CV Dataset Audit Report</h1>
<p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>

<div class="summary">
  <div class="card"><div class="label">Total Images</div><div class="value">{stats.total_images}</div></div>
  <div class="card"><div class="label">Total Labels</div><div class="value">{stats.total_labels}</div></div>
  <div class="card"><div class="label">Total Boxes</div><div class="value">{stats.total_boxes}</div></div>
  <div class="card error"><div class="label">Errors</div><div class="value">{len(errors)}</div></div>
  <div class="card warning"><div class="label">Warnings</div><div class="value">{len(warnings)}</div></div>
</div>

<h2>Images Per Split</h2>
<table>
<tr><th>Split</th><th>Count</th></tr>
{"".join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in stats.images_per_split.items())}
</table>

<h2>Class Distribution</h2>
<table>
<tr><th>ID</th><th>Name</th><th>Count</th></tr>
{"".join(class_rows)}
</table>

<h2>Findings</h2>
<div class="filter-bar">
  <button onclick="filterTable('all')" class="active" id="btn-all">All ({len(findings)})</button>
  <button onclick="filterTable('error')" id="btn-error">Errors ({len(errors)})</button>
  <button onclick="filterTable('warning')" id="btn-warning">Warnings ({len(warnings)})</button>
  <button onclick="filterTable('info')" id="btn-info">Info ({len(infos)})</button>
</div>

<table id="findings-table">
<thead><tr><th>Severity</th><th>Category</th><th>Split</th><th>File</th><th>Message</th></tr></thead>
<tbody>
{_finding_rows(errors)}
{_finding_rows(warnings)}
{_finding_rows(infos)}
</tbody>
</table>

<script>
function filterTable(level) {{
  document.querySelectorAll('.filter-bar button').forEach(b => b.classList.remove('active'));
  document.getElementById('btn-' + level).classList.add('active');
  document.querySelectorAll('#findings-table tbody tr').forEach(row => {{
    if (level === 'all') row.style.display = '';
    else row.style.display = row.classList.contains(level) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')

    return html