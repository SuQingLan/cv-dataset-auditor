"""GitHub API integration for cv-dataset-auditor.

Submit audit reports and open issues on GitHub using the REST API.
Uses only the Python standard library (urllib), no extra dependencies.

The token is read from the GITHUB_TOKEN environment variable and is
never logged or written into any report.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    """Raised when the GitHub API call fails."""


def get_token(env_var: str = "GITHUB_TOKEN") -> Optional[str]:
    """Read a GitHub token from the environment. Never returns a default value."""
    return os.environ.get(env_var) or None


def _request(
    method: str,
    url: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Perform a GitHub API request with bearer authentication.

    Args:
        method: HTTP method (GET, POST, PUT, ...).
        url: Full API URL.
        token: GitHub token for authentication.
        payload: Optional JSON body.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        GitHubAPIError: On HTTP errors (4xx/5xx), with the API error message.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "cv-dataset-auditor/0.1.0",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            data = json.loads(e.read().decode("utf-8"))
            detail = data.get("message", "")
        except Exception:
            pass
        finally:
            # Close the error response stream to avoid leaking file handles.
            try:
                e.close()
            except Exception:
                pass
        raise GitHubAPIError(f"GitHub API {e.code}: {detail or e.reason}") from e
    except urllib.error.URLError as e:
        raise GitHubAPIError(f"Network error: {e.reason}") from e


def create_issue(
    repo: str,
    title: str,
    body: str,
    token: str,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create an issue in the given repository.

    Args:
        repo: "owner/repo" (e.g. "SuQingLan/cv-dataset-auditor").
        title: Issue title.
        body: Issue body (Markdown).
        token: GitHub token.
        labels: Optional issue labels.

    Returns:
        The created issue object.

    Raises:
        GitHubAPIError: On API failure.
    """
    payload: Dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    return _request(
        "POST",
        f"{API_BASE}/repos/{urllib.parse.quote(repo)}/issues",
        token,
        payload,
    )


def upload_file(
    repo: str,
    path: str,
    content: bytes,
    token: str,
    branch: str = "main",
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload a file to a repository using the Contents API (base64-encoded).

    Args:
        repo: "owner/repo".
        path: Path inside the repo (e.g. "reports/audit-2026-10-18.json").
        content: Raw file bytes.
        token: GitHub token.
        branch: Target branch.
        message: Commit message. Auto-generated if None.

    Returns:
        The created/updated content object.

    Raises:
        GitHubAPIError: On API failure.
    """
    import base64

    if message is None:
        message = f"audit: add report {path}"

    payload = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": branch,
    }
    return _request(
        "PUT",
        f"{API_BASE}/repos/{urllib.parse.quote(repo)}/contents/{urllib.parse.quote(path, safe='/')}",
        token,
        payload,
    )


def build_issue_body(report: Dict[str, Any]) -> str:
    """Build a Markdown issue body summarizing an audit report.

    Args:
        report: The report dict produced by generate_json_report.

    Returns:
        Markdown string suitable for an issue body.
    """
    summary = report.get("summary", {})
    findings = report.get("findings", [])
    images_per_split = report.get("images_per_split", {})
    class_distribution = report.get("class_distribution", {})

    lines = [
        "## 审计摘要（自动生成）",
        "",
        f"- **审计时间**: {report.get('audit_time', '')}",
        f"- **图片总数**: {summary.get('total_images', 0)}",
        f"- **标注总数**: {summary.get('total_labels', 0)}",
        f"- **标注框总数**: {summary.get('total_boxes', 0)}",
        "",
        "## Findings 统计",
        "",
        f"- 🔴 **Error**: {summary.get('errors', 0)}",
        f"- 🟡 **Warning**: {summary.get('warnings', 0)}",
        f"- 🔵 **Info**: {summary.get('info', 0)}",
        "",
    ]

    if images_per_split:
        lines.append("## 各 Split 图片数")
        lines.append("")
        lines.append("| Split | 图片数 |")
        lines.append("|-------|--------|")
        for split, count in images_per_split.items():
            lines.append(f"| {split} | {count} |")
        lines.append("")

    if class_distribution:
        lines.append("## 类别分布")
        lines.append("")
        lines.append("| class_id | 数量 |")
        lines.append("|----------|------|")
        for cls_id in sorted(class_distribution):
            lines.append(f"| {cls_id} | {class_distribution[cls_id]} |")
        lines.append("")

    if findings:
        lines.append("## 问题清单")
        lines.append("")
        lines.append("| 级别 | 类别 | 文件 | 说明 |")
        lines.append("|------|------|------|------|")
        for f_ in findings[:50]:  # cap to keep issue readable
            file_name = f_.get("file", "")
            lines.append(
                f"| {f_.get('severity', '')} | {f_.get('category', '')} | "
                f"`{file_name}` | {f_.get('message', '')} |"
            )
        if len(findings) > 50:
            lines.append(f"| ... | 共 {len(findings)} 条，以上仅显示前 50 条 | | |")
        lines.append("")

    lines.append(
        "---\n*本 Issue 由 `cv-dataset-auditor` 自动生成。"
        "使用 `--gh-repo owner/repo --gh-token <env:GITHUB_TOKEN>` 复现。*"
    )
    return "\n".join(lines)


def submit_audit_issue(
    repo: str,
    report: Dict[str, Any],
    token: str,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create an audit report issue for a repository.

    Args:
        repo: "owner/repo".
        report: Audit report dict.
        token: GitHub token.
        labels: Optional labels.

    Returns:
        The created issue object.

    Raises:
        GitHubAPIError: On API failure.
    """
    summary = report.get("summary", {})
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = (
        f"[cv-audit] {summary.get('total_images', 0)} images, "
        f"{summary.get('errors', 0)} errors, {summary.get('warnings', 0)} warnings ({stamp})"
    )
    body = build_issue_body(report)
    return create_issue(repo, title, body, token, labels=labels)