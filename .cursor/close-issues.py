"""Close SonarCloud issues resolved by the security hardening commits on dev.

Requires GITHUB_TOKEN (or GH_TOKEN) in the environment with `repo` scope.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = "kiet-ta/ar-ai-exe"
API_BASE = "https://api.github.com"

ISSUE_CLOSE_COMMENTS = {
    10: "Closed: BLOCKER path-traversal in `backend/app/scripts/seed_desktop_demo_project.py:210` (S2083). Resolved by `app/core/path_safety.py::resolve_existing_file` and the `validate_demo_model_path` guard that enforces an allowed extension and `strict=True` resolution. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    11: "Closed: BLOCKER path-traversal in `backend/app/services/export_packages.py:268` (S2083). The MTL/JSON/zip paths are now built via `safe_child_path`/`ensure_path_within` from `app/core/path_safety.py`, which rejects absolute or traversal inputs. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    12: "Closed: BLOCKER path-traversal in `backend/app/services/mesh_cleanup.py:171` (S2083). The MTL writer is now confined to the cleanup output dir; combined with the new path safety helpers in `app/core/path_safety.py`, user-controlled paths can no longer escape the work directory. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    13: "Closed: BLOCKER client-side redirection in `frontend/src/App.tsx` (S6105). `projectId`/path inputs are now passed through `sanitizeProjectId` (regex `/^[A-Za-z0-9_-]{3,120}$/`) and `openDesktopProjectId`/`loginRedirectUrl` only emit URLSearchParams + relative paths. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    14: "Closed: CRITICAL IndexError in `backend/tests/test_mesh_cleanup.py:64` (S6466). The assertion was rewritten from `runner.command[:3] == [...]` (potential IndexError on short lists) to explicit `runner.command[0]/[1]/[2]` equality checks guarded by `len(runner.command) >= 3`. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    15: "Closed: HIGH S7637 in `.github/workflows/backend-ci.yml:50`. `astral-sh/setup-uv@v5` is now pinned to commit SHA `d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86` (with `# v5` comment) in commit 5c2b999 on `dev`.",
    16: "Closed: HIGH S7637 in `.github/workflows/mobile-ci.yml:35`. `subosito/flutter-action@v2` is now pinned to commit SHA `1a449444c387b1966244ae4d4f8c696479add0b2` (with `# v2` comment) in commit 5c2b999 on `dev`.",
    17: "Closed: HIGH S7637 in `.github/workflows/sonarcloud.yml:72`. `SonarSource/sonarqube-scan-action@v8.2.0` is now pinned to commit SHA `713881670b6b3676cda39549040e2d88c70d582e` (with `# v8.2.0` comment) in commit 5c2b999 on `dev`.",
    18: "Closed: HIGH LLM path escape in `backend/app/scripts/seed_desktop_demo_project.py:219` (S8707). `glb_path` is now passed through `validate_demo_model_path` which calls `resolve_existing_file` with a `{'.glb', '.gltf'}` allowlist and `strict=True`. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    19: "Closed: HIGH tainted URL construction in `frontend/src/api/client.ts:31` (S8476). `apiUrl` now requires `http(s):`, rejects control characters, forbids embedded credentials, confines to the configured base origin, and rejects `/api` path traversal. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    20: "Closed: HIGH tainted data written to browser storage in `frontend/src/api/client.ts:79` (S8475). Token persistence now goes through `frontend/src/api/authStorage.ts::storeAccessToken`, which validates the access token against `^[A-Za-z0-9._~+/=-]+$`, length 16-4096, before calling `localStorage.setItem`. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    21: "Closed: HIGH tainted URL construction in `frontend/src/api/client.ts:220` (S8476). Same fix as issue #19: the `apiUrl` helper now sanitizes paths and rejects non-HTTP(S) or off-origin URLs before `fetch`. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    22: "Closed: HIGH tainted URL construction in `frontend/src/api/client.ts:235` (S8476). Same fix as issue #19: `apiUrl` now requires `http(s):`, rejects control characters, and enforces the configured API origin. Cherry-picked from 93cb62c in commit 6bd4615 on `dev`.",
    23: "Closed: HIGH missing release obfuscation in `mobile/android/app/build.gradle.kts:34` (S7204). The `release` buildType now enables `isMinifyEnabled = true`, `isShrinkResources = true`, and references `proguard-rules.pro` (new file) in commit 5c2b999 on `dev`.",
}


def request(method, url, token, body=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "ar-ai-exe-security-bot",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("ERROR: set GITHUB_TOKEN (or GH_TOKEN) with `repo` scope.", file=sys.stderr)
        return 2

    issues_path = Path(__file__).resolve().parent / "issues.json"
    data = json.loads(issues_path.read_text(encoding="utf-8"))
    issues = [i for i in data if not i.get("pull_request") and i["state"] == "open"]

    for issue in issues:
        number = issue["number"]
        if number not in ISSUE_CLOSE_COMMENTS:
            print(f"skip #{number} (no close message)")
            continue
        comment = ISSUE_CLOSE_COMMENTS[number]
        print(f"comment on #{number}: {issue['title'][:80]}")
        request(
            "POST",
            f"{API_BASE}/repos/{REPO}/issues/{number}/comments",
            token,
            {"body": comment},
        )
        print(f"close #{number}")
        request(
            "PATCH",
            f"{API_BASE}/repos/{REPO}/issues/{number}",
            token,
            {"state": "closed", "state_reason": "completed"},
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
