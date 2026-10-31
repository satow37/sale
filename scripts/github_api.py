"""GitHub Issue の操作(投稿候補の承認フロー用)"""
import os

import requests

API = "https://api.github.com"


def _req(method, path, **kw):
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    r = requests.request(
        method, f"{API}/repos/{repo}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=30, **kw,
    )
    if not r.ok:
        raise RuntimeError(f"GitHub APIエラー {r.status_code}: {r.text[:300]}")
    return r.json()


def create_issue(title, body):
    return _req("POST", "/issues", json={"title": title, "body": body})["number"]


def comment(number, body):
    _req("POST", f"/issues/{number}/comments", json={"body": body})


def close_issue(number):
    _req("PATCH", f"/issues/{number}", json={"state": "closed"})


def get_issue(number):
    return _req("GET", f"/issues/{number}")
