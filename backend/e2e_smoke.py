"""End-to-end smoke test against the running backend."""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api"
TOKEN = "local-demo-token-change-me"

def call(method, path, *, body=None, headers=None, expect_json=True):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if expect_json and raw else raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        return e.code, json.loads(raw) if raw else {}

def main() -> int:
    code, health = call("GET", "/../health")
    # 307 to /health; follow manually
    print("[1] health:", code, health)

    code, login = call("POST", "/auth/demo-login")
    print("[2] demo-login:", code, login.get("user", {}).get("email"))

    code, projects = call("GET", "/projects")
    print("[3] list-projects:", code, "count:", len(projects.get("items", [])))

    if not projects.get("items"):
        print("  (no project yet, creating one)")
        code, proj = call("POST", "/projects", body={
            "name": "E2E Mobile Scan",
            "sourceType": "scan",
        })
        print("  created:", code, proj.get("id"))
    else:
        proj = projects["items"][0]
    pid = proj["id"]

    code, scan = call("POST", "/scan-sessions", body={
        "metadata": {
            "shoe": {"sizeSystem": "EU", "size": "42", "side": "right", "type": "sneaker",
                     "material": "canvas", "condition": "new"},
            "measurements": {"lengthCm": 28, "widthCm": 10},
            "scanSetup": {"calibrationReference": "calib_001", "lighting": "natural", "background": "plain"},
            "customizationGoal": ["add stickers"],
        },
        "projectId": pid,
    })
    print("[4] create-scan-session:", code, scan.get("id"))
    sid = scan.get("id", "")

    if sid:
        code, st = call("GET", f"/scan-sessions/{sid}/status")
        print("[5] scan-status:", code, st.get("status"))

    code, ctx = call("GET", f"/projects/{pid}/editor-context")
    print("[6] editor-context:", code, "perms:", ctx.get("permissions"))

    code, design = call("POST", f"/projects/{pid}/designs", body={
        "designConfig": {"version": 1, "layers": []},
        "name": "Initial Design",
    })
    print("[7] create-design:", code, design.get("error") or design.get("id"))

    return 0

if __name__ == "__main__":
    sys.exit(main())
