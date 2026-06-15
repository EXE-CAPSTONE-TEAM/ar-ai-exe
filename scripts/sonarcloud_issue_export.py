#!/usr/bin/env python3
"""Create GitHub Issues for high-risk SonarCloud BUG/VULNERABILITY findings.

The script intentionally uses only stdlib HTTP clients so the GitHub Action does
not need extra dependencies or local credentials. Tokens are read from env vars.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

TARGET_TYPES = {"BUG", "VULNERABILITY"}
TARGET_SEVERITIES = {"BLOCKER", "CRITICAL", "HIGH"}
DEFAULT_LABELS = ["security", "bug", "sonarqube", "priority: high"]
LABEL_COLORS = {
    "security": "b60205",
    "bug": "d73a4a",
    "sonarqube": "1f6feb",
    "priority: high": "fbca04",
}


def main() -> int:
    sonar_token = required_env("SONAR_TOKEN")
    github_token = required_env("GITHUB_TOKEN")
    project_key = required_env("SONAR_PROJECT_KEY")
    repository = required_env("GITHUB_REPOSITORY")
    sonar_host = os.getenv("SONAR_HOST_URL", "https://sonarcloud.io").rstrip("/")
    labels = parse_labels(os.getenv("SONAR_FINDING_LABELS"))
    max_issues = int(os.getenv("SONAR_MAX_ISSUES", "100"))

    sonar = SonarClient(sonar_host, sonar_token)
    github = GitHubClient(repository, github_token)

    findings = sonar.search_high_risk_findings(project_key)
    print(f"SonarCloud returned {len(findings)} matching high-risk findings.")

    if not findings:
        return 0

    for label in labels:
        github.ensure_label(label)

    created = 0
    skipped = 0
    for issue in findings[:max_issues]:
        marker = sonar_marker(issue["key"])
        if github.open_issue_exists(marker):
            skipped += 1
            continue
        github.create_issue(
            title=issue_title(issue, project_key),
            body=issue_body(issue, project_key, sonar_host, marker),
            labels=labels,
        )
        created += 1
        time.sleep(0.25)

    if len(findings) > max_issues:
        print(f"Skipped {len(findings) - max_issues} findings because SONAR_MAX_ISSUES={max_issues}.")

    print(f"Created {created} GitHub issues, skipped {skipped} duplicates.")
    return 0


class SonarClient:
    def __init__(self, host: str, token: str) -> None:
        self.host = host
        self.token = token

    def search_high_risk_findings(self, project_key: str) -> list[dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        queries = [
            {"types": "BUG,VULNERABILITY", "severities": "BLOCKER,CRITICAL"},
            {"impactSoftwareQualities": "SECURITY,RELIABILITY", "impactSeverities": "BLOCKER,HIGH"},
        ]

        for query in queries:
            for issue in self._search_pages(project_key, query):
                if is_code_fixable(issue) and matches_policy(issue):
                    candidates[issue["key"]] = issue

        return sorted(
            candidates.values(),
            key=lambda issue: (
                severity_rank(issue),
                component_path(issue, project_key),
                issue.get("line") or 0,
            ),
        )

    def _search_pages(self, project_key: str, query: dict[str, str]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        page = 1
        page_size = 500
        while True:
            params = {
                "componentKeys": project_key,
                "resolved": "false",
                "ps": str(page_size),
                "p": str(page),
                **query,
            }
            try:
                data = self.get_json("/api/issues/search", params)
            except RuntimeError as exc:
                print(f"::warning::{exc}", file=sys.stderr)
                break

            page_issues = data.get("issues", [])
            if not isinstance(page_issues, list):
                break
            issues.extend(page_issues)

            paging = data.get("paging", {})
            total = int(paging.get("total", data.get("total", len(issues))))
            if page * page_size >= total or not page_issues:
                break
            page += 1

        return issues

    def get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.host}{path}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"SonarCloud API request failed with {exc.code}: {body[:400]}") from exc


class GitHubClient:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.token = token

    def ensure_label(self, name: str) -> None:
        encoded = urllib.parse.quote(name, safe="")
        response = self.request("GET", f"/repos/{self.repository}/labels/{encoded}", expected=(200, 404))
        if response["status"] == 200:
            return
        payload = {
            "name": name,
            "color": LABEL_COLORS.get(name, "ededed"),
            "description": "Created by SonarCloud automation.",
        }
        self.request("POST", f"/repos/{self.repository}/labels", payload=payload, expected=(201, 422))

    def open_issue_exists(self, marker: str) -> bool:
        query = f'repo:{self.repository} is:issue is:open "{marker}"'
        params = urllib.parse.urlencode({"q": query, "per_page": "1"})
        response = self.request("GET", f"/search/issues?{params}", expected=(200,))
        return int(response["data"].get("total_count", 0)) > 0

    def create_issue(self, title: str, body: str, labels: list[str]) -> None:
        self.request(
            "POST",
            f"/repos/{self.repository}/issues",
            payload={"title": title, "body": body, "labels": labels},
            expected=(201,),
        )

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.github.com{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return {"status": response.status, "data": json.loads(body) if body else {}}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in expected:
                return {"status": exc.code, "data": json.loads(body) if body else {}}
            raise RuntimeError(f"GitHub API request failed with {exc.code}: {body[:400]}") from exc


def matches_policy(issue: dict[str, Any]) -> bool:
    issue_type = str(issue.get("type", "")).upper()
    impacts = issue.get("impacts") or []
    impact_qualities = {str(impact.get("softwareQuality", "")).upper() for impact in impacts}

    if issue_type and issue_type not in TARGET_TYPES:
        return False
    if not issue_type and not (impact_qualities & {"SECURITY", "RELIABILITY"}):
        return False

    classic_severity = str(issue.get("severity", "")).upper()
    impact_severities = {str(impact.get("severity", "")).upper() for impact in impacts}
    return classic_severity in TARGET_SEVERITIES or bool(impact_severities & TARGET_SEVERITIES)


def is_code_fixable(issue: dict[str, Any]) -> bool:
    return bool(issue.get("key") and issue.get("component"))


def severity_rank(issue: dict[str, Any]) -> int:
    order = {"BLOCKER": 0, "CRITICAL": 1, "HIGH": 2}
    severities = [str(issue.get("severity", "")).upper()]
    severities.extend(str(impact.get("severity", "")).upper() for impact in issue.get("impacts") or [])
    return min((order.get(severity, 99) for severity in severities), default=99)


def component_path(issue: dict[str, Any], project_key: str) -> str:
    component = str(issue.get("component", "unknown"))
    prefix = f"{project_key}:"
    return component.removeprefix(prefix)


def issue_title(issue: dict[str, Any], project_key: str) -> str:
    severity = best_severity(issue)
    issue_type = str(issue.get("type") or "Finding").title()
    path = component_path(issue, project_key)
    line = f":{issue['line']}" if issue.get("line") else ""
    return trim(f"SonarCloud {severity} {issue_type}: {path}{line}", 240)


def issue_body(issue: dict[str, Any], project_key: str, sonar_host: str, marker: str) -> str:
    path = component_path(issue, project_key)
    line = issue.get("line")
    rule = issue.get("rule", "n/a")
    severity = best_severity(issue)
    issue_type = issue.get("type", "n/a")
    message = issue.get("message", "No SonarCloud message provided.")
    issue_key = issue["key"]
    sonar_url = f"{sonar_host}/project/issues?open={urllib.parse.quote(issue_key)}&id={urllib.parse.quote(project_key)}"

    return f"""## Finding

- Type: `{issue_type}`
- Severity: `{severity}`
- Rule: `{rule}`
- File: `{path}`
- Line: `{line or "n/a"}`
- SonarCloud issue: [{issue_key}]({sonar_url})

## SonarCloud message

{message}

## Acceptance criteria

- [ ] Root cause is fixed in code or dependency manifest.
- [ ] Relevant test/build/lint command is run.
- [ ] SonarCloud no longer reports this finding after the next scan.

{marker}
"""


def best_severity(issue: dict[str, Any]) -> str:
    values = [str(issue.get("severity", "")).upper()]
    values.extend(str(impact.get("severity", "")).upper() for impact in issue.get("impacts") or [])
    ranked = sorted((value for value in values if value), key=lambda value: severity_rank({"severity": value}))
    return ranked[0] if ranked else "UNKNOWN"


def sonar_marker(issue_key: str) -> str:
    return f"<!-- sonar-issue-key:{issue_key} -->"


def parse_labels(value: str | None) -> list[str]:
    if not value:
        return DEFAULT_LABELS
    labels = [label.strip() for label in value.split(",") if label.strip()]
    return labels or DEFAULT_LABELS


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def trim(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "..."


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
