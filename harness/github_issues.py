#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Audit, report, and close GitHub issues without exposing the credential.

This is the only supported GitHub boundary for the phase pipeline. It obtains
an existing GitHub credential through ``git credential fill`` in a subprocess,
keeps the password in memory, and sends it only in an HTTP Authorization header.
It never prints the credential, accepts it as an argument, or writes it to a
file. Output is JSON and contains issue data only.

The repository is fixed because the harness publishes Clio and must never infer
a different repository from the nested private checkout.

Commands (run from the public repository root):

    python3 private/clio-private/harness/github_issues.py list-open
    python3 private/clio-private/harness/github_issues.py search-open "error text"
    python3 private/clio-private/harness/github_issues.py view 123
    python3 private/clio-private/harness/github_issues.py report-bug \
      --title-file <public-safe-title.txt> \
      --body-file <public-safe-report.md>
    python3 private/clio-private/harness/github_issues.py close 123 \
      --expected-digest <sha256> --commit <public-commit-sha> \
      --comment-file <public-safe-comment.md>
    python3 private/clio-private/harness/github_issues.py ledger-list \
      --ledger-file <run-dir>/reported-bugs.json
    python3 private/clio-private/harness/github_issues.py ledger-add \
      --ledger-file <run-dir>/reported-bugs.json \
      --number 123 --title "Public title" --url "https://github.com/heyaibi/clio/issues/123"
    python3 private/clio-private/harness/github_issues.py --self-test

Read model: ``list-open`` and ``search-open`` return light triage records
(title, body, labels, state, URL, comment count, no comment bodies) so a full
audit never pays one comment-list call per issue. ``view`` returns the full
thread plus the authoritative ``audit_digest`` used for closing. Candidate
digests must always come from ``view``, never from triage output.

Closing is idempotent. The helper adds an invisible commit marker to the
closing comment. If a retry finds that marker on an already-closed issue, it
reports success without posting a duplicate. Public issue text is rejected when
it contains private harness paths, private phase numbers, or credential-like
content.

Duplicate guard model: live search is eventually consistent, so stages also
keep a run-local ``reported-bugs.json`` ledger. Every stage reads the ledger
before searching and appends to it after a successful ``report-bug``; a ledger
hit counts as an equivalent issue even when search misses it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
REPOSITORY = "heyaibi/clio"
API_VERSION = "2022-11-28"
HTTP_TIMEOUT_S = 30
CREDENTIAL_TIMEOUT_S = 30
PAGE_SIZE = 100
MAX_PUBLIC_TEXT_BYTES = 60_000
MARKER_PREFIX = "<!-- clio-harness-addressed:issue="
MARKER_COMMIT_PREFIX = ":commit="
COMMIT_RE = re.compile(r"[0-9a-f]{7,64}")
DIGEST_RE = re.compile(r"[0-9a-f]{64}")
FORBIDDEN_PUBLIC_PATTERNS = (
    re.compile(r"(?i)\bprivate[\\/]"),
    re.compile(r"(?i)\bclio-private\b"),
    re.compile(r"(?i)\broadmap[\\/]"),
    re.compile(r"(?i)\bruns[\\/]"),
    re.compile(r"(?i)\bbaseline[\\/]"),
    re.compile(r"(?i)\bphase[- #]?\d{4,6}\b"),
    re.compile(r"(?i)\bAuthorization\s*:"),
    re.compile(r"(?i)\bBearer\s+"),
    re.compile(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*\S+"
    ),
)


class GitHubError(Exception):
    """A sanitized GitHub operation failure safe to print."""


def load_token() -> str:
    """Read the configured GitHub credential without exposing helper output."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    try:
        process = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            timeout=CREDENTIAL_TIMEOUT_S,
            env=env,
            check=False,
        )
    except FileNotFoundError:
        raise GitHubError("git is not available for GitHub authentication") from None
    except subprocess.TimeoutExpired:
        raise GitHubError("GitHub credential lookup timed out") from None

    fields: dict[str, str] = {}
    for line in process.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            fields[key] = value
    token = fields.get("password", "")
    if process.returncode != 0 or not token:
        raise GitHubError("no GitHub credential is available")
    return token


def validate_public_text(text: str, label: str) -> None:
    """Reject content that would leak private harness material or credentials."""
    encoded = text.encode("utf-8")
    if not text.strip():
        raise GitHubError(f"{label} is empty")
    if len(encoded) > MAX_PUBLIC_TEXT_BYTES:
        raise GitHubError(f"{label} exceeds the safe size limit")
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        if pattern.search(text):
            raise GitHubError(f"{label} contains forbidden private or credential-like text")


def marker_for(number: int, commit: str) -> str:
    if number <= 0:
        raise GitHubError("issue number must be positive")
    if not COMMIT_RE.fullmatch(commit):
        raise GitHubError("commit must be 7-64 lowercase hexadecimal characters")
    return f"{MARKER_PREFIX}{number}{MARKER_COMMIT_PREFIX}{commit} -->"


def audit_digest(issue: dict[str, Any]) -> str:
    """Hash the material used for an issue audit, excluding volatile fields."""
    material = {
        "number": issue.get("number"),
        "title": issue.get("title", ""),
        "body": issue.get("body") or "",
        "labels": issue.get("labels", []),
        "comments": issue.get("comments", []),
        "url": issue.get("url", ""),
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def triage_digest(issue: dict[str, Any]) -> str:
    """Hash the light triage record (no comment bodies) for screening."""
    material = {
        "number": issue.get("number"),
        "title": issue.get("title", ""),
        "body": issue.get("body") or "",
        "labels": issue.get("labels", []),
        "url": issue.get("url", ""),
        "comment_count": issue.get("comment_count", 0),
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def digest_without_marker(issue: dict[str, Any], marker: str) -> str:
    """Hash issue content while ignoring this run's retry marker comment."""
    comparable = dict(issue)
    comparable["comments"] = [
        comment
        for comment in issue.get("comments", [])
        if marker not in (comment.get("body") or "")
    ]
    return audit_digest(comparable)


def load_ledger(path: Path) -> list[dict[str, Any]]:
    """Read the run-local reported-bugs ledger (empty list when absent)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as error:
        raise GitHubError(f"reported-bugs ledger is unreadable: {error}") from None
    if not isinstance(raw, list):
        raise GitHubError("reported-bugs ledger must be a JSON list")
    entries: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("number"), int):
            raise GitHubError("reported-bugs ledger holds {number, title, url} objects")
        entries.append(
            {
                "number": item["number"],
                "title": item.get("title", ""),
                "url": item.get("url", ""),
            }
        )
    return entries


def ledger_add(path: Path, number: int, title: str, url: str) -> dict[str, Any]:
    """Append one reported bug to the run-local ledger (deduplicated by number)."""
    if number <= 0:
        raise GitHubError("issue number must be positive")
    if not title.strip():
        raise GitHubError("ledger title is empty")
    if not url.strip():
        raise GitHubError("ledger url is empty")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise GitHubError(f"cannot create the ledger directory: {error}") from None
    entries = load_ledger(path)
    if not any(entry["number"] == number for entry in entries):
        entries.append({"number": number, "title": title.strip(), "url": url.strip()})
        try:
            path.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")
        except OSError as error:
            raise GitHubError(f"cannot write the ledger: {error}") from None
    return {"ok": True, "ledger": str(path), "entries": entries}


class GitHubClient:
    """Minimal GitHub Issues API client with one private in-memory token."""

    def __init__(self, token: str) -> None:
        self._token = token

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{API_ROOT}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "clio-phase-harness",
            },
        )
        try:
            with urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
                body = response.read()
        except HTTPError as error:
            raise GitHubError(
                f"GitHub API request failed: HTTP {error.code} {error.reason}"
            ) from None
        except URLError as error:
            raise GitHubError(f"GitHub API request failed: {error.reason}") from None
        except TimeoutError:
            raise GitHubError("GitHub API request timed out") from None
        if not body:
            return {}
        try:
            return json.loads(body)
        except ValueError:
            raise GitHubError("GitHub API returned invalid JSON") from None

    def paginate(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            query = dict(params, per_page=PAGE_SIZE, page=page)
            batch = self.request("GET", f"{path}?{urlencode(query)}")
            if not isinstance(batch, list):
                raise GitHubError("GitHub API returned an unexpected issue list")
            items.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < PAGE_SIZE:
                return items
            page += 1

    def comments(self, number: int) -> list[dict[str, Any]]:
        path = f"/repos/{REPOSITORY}/issues/{number}/comments"
        return self.paginate(path, {})

    @staticmethod
    def _labels(raw: dict[str, Any]) -> list[str]:
        return sorted(
            label.get("name", "") for label in raw.get("labels", []) if isinstance(label, dict)
        )

    @staticmethod
    def _comment_count(raw: dict[str, Any], comments: list[dict[str, Any]]) -> int:
        count = raw.get("comments")
        if isinstance(count, int) and count >= 0:
            return count
        return len(comments)

    def compact_issue(self, raw: dict[str, Any], comments: list[dict[str, Any]]) -> dict[str, Any]:
        """Full issue record with comment bodies and the closing audit digest."""
        compact_comments = [
            {
                "author": (comment.get("user") or {}).get("login", ""),
                "body": comment.get("body") or "",
                "created_at": comment.get("created_at", ""),
            }
            for comment in comments
        ]
        issue = {
            "number": raw.get("number"),
            "title": raw.get("title", ""),
            "body": raw.get("body") or "",
            "labels": self._labels(raw),
            "state": raw.get("state", ""),
            "state_reason": raw.get("state_reason"),
            "url": raw.get("html_url", ""),
            "updated_at": raw.get("updated_at", ""),
            "comment_count": self._comment_count(raw, comments),
            "comments_truncated": False,
            "comments": compact_comments,
        }
        issue["audit_digest"] = audit_digest(issue)
        return issue

    def triage_issue(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Light screening record: no comment fetch, no comment bodies."""
        count = raw.get("comments")
        comment_count = count if isinstance(count, int) and count >= 0 else 0
        issue = {
            "number": raw.get("number"),
            "title": raw.get("title", ""),
            "body": raw.get("body") or "",
            "labels": self._labels(raw),
            "state": raw.get("state", ""),
            "state_reason": raw.get("state_reason"),
            "url": raw.get("html_url", ""),
            "updated_at": raw.get("updated_at", ""),
            "comment_count": comment_count,
            "comments_truncated": comment_count > 0,
            "comments": [],
        }
        issue["triage_digest"] = triage_digest(issue)
        return issue

    def issue(self, number: int) -> dict[str, Any]:
        raw = self.request("GET", f"/repos/{REPOSITORY}/issues/{number}")
        if not isinstance(raw, dict):
            raise GitHubError("GitHub API returned an unexpected issue")
        if "pull_request" in raw:
            raise GitHubError(f"#{number} is a pull request, not an issue")
        return self.compact_issue(raw, self.comments(number))

    def list_open(self) -> list[dict[str, Any]]:
        """List open issues as light triage records (no per-issue comment calls)."""
        path = f"/repos/{REPOSITORY}/issues"
        raw_issues = self.paginate(path, {"state": "open"})
        return [
            self.triage_issue(raw)
            for raw in raw_issues
            if "pull_request" not in raw and isinstance(raw.get("number"), int)
        ]

    def search_open(self, query: str) -> list[dict[str, Any]]:
        """Search open issues for duplicate-bug checks using a narrow query.

        Returns light triage records only; comment bodies are never fetched
        here because duplicate screening needs titles and bodies, not threads.
        """
        terms = query.strip()
        validate_public_text(terms, "search query")
        if len(terms) > 256:
            raise GitHubError("search query exceeds GitHub's 256-character limit")
        search = f"repo:{REPOSITORY} is:issue is:open {terms}"
        matches: list[dict[str, Any]] = []
        page = 1
        while True:
            result = self.request(
                "GET",
                f"/search/issues?{urlencode({'q': search, 'per_page': PAGE_SIZE, 'page': page})}",
            )
            if not isinstance(result, dict) or not isinstance(result.get("items"), list):
                raise GitHubError("GitHub API returned an unexpected search result")
            if result.get("incomplete_results"):
                raise GitHubError("GitHub issue search was incomplete; use narrower terms")
            total = result.get("total_count", 0)
            if not isinstance(total, int) or total < 0:
                raise GitHubError("GitHub API returned an invalid search count")
            if total > 1000:
                raise GitHubError("duplicate search is too broad; use narrower error terms")
            batch = [item for item in result["items"] if isinstance(item, dict)]
            matches.extend(
                self.triage_issue(item)
                for item in batch
                if "pull_request" not in item and isinstance(item.get("number"), int)
            )
            if page * PAGE_SIZE >= total:
                return matches
            page += 1

    def create_issue(self, title: str, body: str) -> dict[str, Any]:
        created = self.request(
            "POST",
            f"/repos/{REPOSITORY}/issues",
            {"title": title, "body": body},
        )
        if not isinstance(created, dict) or not isinstance(created.get("number"), int):
            raise GitHubError("GitHub API did not return the created issue")
        return {
            "ok": True,
            "number": created["number"],
            "state": created.get("state", "open"),
            "url": created.get("html_url", ""),
        }

    def add_comment(self, number: int, body: str) -> None:
        self.request("POST", f"/repos/{REPOSITORY}/issues/{number}/comments", {"body": body})

    def close(self, number: int) -> None:
        self.request(
            "PATCH",
            f"/repos/{REPOSITORY}/issues/{number}",
            {"state": "closed", "state_reason": "completed"},
        )


def close_issue(
    client: GitHubClient,
    number: int,
    expected_digest: str,
    commit: str,
    comment: str,
) -> dict[str, Any]:
    """Close one audited issue, with a retry-safe comment marker."""
    if not DIGEST_RE.fullmatch(expected_digest):
        raise GitHubError("expected audit digest must be 64 lowercase hexadecimal characters")
    validate_public_text(comment, "closing comment")
    if commit not in comment:
        raise GitHubError("closing comment must cite the pushed commit")
    marker = marker_for(number, commit)
    issue = client.issue(number)
    existing = any(marker in (comment.get("body") or "") for comment in issue["comments"])
    if issue["state"] != "open":
        if existing and issue.get("state_reason") == "completed":
            return {"ok": True, "number": number, "state": "closed", "already_closed": True}
        raise GitHubError(f"#{number} closed after the audit without this run's completed marker")
    if digest_without_marker(issue, marker) != expected_digest:
        raise GitHubError(f"#{number} changed after the audit; refusing to close it")

    comment_posted = False
    if not existing:
        client.add_comment(number, f"{comment}\n\n{marker}")
        comment_posted = True
    current = client.issue(number)
    if current["state"] != "open":
        if (
            current.get("state_reason") == "completed"
            and any(marker in (item.get("body") or "") for item in current["comments"])
        ):
            return {"ok": True, "number": number, "state": "closed", "already_closed": True}
        raise GitHubError(f"#{number} closed before the final check")
    if digest_without_marker(current, marker) != expected_digest:
        raise GitHubError(f"#{number} changed while closing; refusing to close it")
    client.close(number)
    final = client.issue(number)
    if final["state"] != "closed" or final.get("state_reason") != "completed":
        raise GitHubError(f"#{number} did not reach the completed-closed state")
    return {
        "ok": True,
        "number": number,
        "state": final["state"],
        "already_closed": False,
        "comment_posted": comment_posted,
    }


def self_test() -> int:
    """Exercise credential parsing and secret handling without network access."""
    credential = SimpleNamespace(
        returncode=0,
        stdout="protocol=https\nhost=github.com\nusername=tester\npassword=a=b\n",
    )
    with patch.object(subprocess, "run", return_value=credential):
        assert load_token() == "a=b"

    validate_public_text("Fixed by the public commit and covered by tests.", "comment")
    for unsafe in (
        "See private/clio-private/runs/phase-100060/findings.json",
        "Phase 100060 passed",
        "Authorization: Bearer secret",
        "github_pat_" + "not_a_real_token",
        "password" + "=unit-test-value",
        "-----BEGIN PRIVATE KEY-----",
    ):
        try:
            validate_public_text(unsafe, "comment")
        except GitHubError:
            pass
        else:
            raise AssertionError(f"unsafe comment accepted: {unsafe}")

    class FakeIssueClient:
        def __init__(self):
            self.data = {
                "number": 7,
                "title": "Public failure",
                "body": "Reproduction",
                "labels": ["bug"],
                "state": "open",
                "state_reason": None,
                "url": "https://github.com/heyaibi/clio/issues/7",
                "updated_at": "2026-09-24T00:00:00Z",
                "comments": [],
            }
            self.data["audit_digest"] = audit_digest(self.data)
            self.comment_count = 0
            self.fail_next_close = False

        def issue(self, _number):
            return json.loads(json.dumps(self.data))

        def add_comment(self, _number, body):
            self.data["comments"].append({"body": body})
            self.comment_count += 1

        def close(self, _number):
            if self.fail_next_close:
                self.fail_next_close = False
                raise GitHubError("simulated close failure")
            self.data["state"] = "closed"
            self.data["state_reason"] = "completed"

    fake_issue_client = FakeIssueClient()
    commit = "a" * 40
    closing_comment = f"Fixed by public commit {commit} and covered by tests."
    first_close = close_issue(
        fake_issue_client,
        7,
        fake_issue_client.data["audit_digest"],
        commit,
        closing_comment,
    )
    assert first_close["state"] == "closed" and first_close["comment_posted"]
    assert marker_for(7, commit) in fake_issue_client.data["comments"][0]["body"]
    assert marker_for(8, commit) not in fake_issue_client.data["comments"][0]["body"]
    retry_close = close_issue(
        fake_issue_client,
        7,
        fake_issue_client.data["audit_digest"],
        commit,
        closing_comment,
    )
    assert retry_close["already_closed"]
    assert fake_issue_client.comment_count == 1

    retry_client = FakeIssueClient()
    retry_client.fail_next_close = True
    try:
        close_issue(
            retry_client,
            7,
            retry_client.data["audit_digest"],
            commit,
            closing_comment,
        )
    except GitHubError:
        pass
    else:
        raise AssertionError("simulated close failure did not propagate")
    recovered_close = close_issue(
        retry_client,
        7,
        retry_client.data["audit_digest"],
        commit,
        closing_comment,
    )
    assert recovered_close["state"] == "closed"
    assert not recovered_close["comment_posted"]
    assert retry_client.comment_count == 1

    import tempfile as _tempfile

    with _tempfile.TemporaryDirectory(prefix="github-issues-ledger") as ledger_dir:
        ledger_path = Path(ledger_dir) / "reported-bugs.json"
        assert load_ledger(ledger_path) == []
        added = ledger_add(
            ledger_path, 11, "Public failure", "https://github.com/heyaibi/clio/issues/11"
        )
        assert len(added["entries"]) == 1
        repeated = ledger_add(
            ledger_path, 11, "Public failure", "https://github.com/heyaibi/clio/issues/11"
        )
        assert len(repeated["entries"]) == 1
        assert load_ledger(ledger_path)[0]["number"] == 11

    raw_triage = {
        "number": 12,
        "title": "Public failure",
        "body": "Reproduction",
        "labels": [{"name": "bug"}],
        "state": "open",
        "state_reason": None,
        "html_url": "https://github.com/heyaibi/clio/issues/12",
        "updated_at": "2026-09-24T00:00:00Z",
        "comments": 7,
    }
    triaged = GitHubClient("unused").triage_issue(raw_triage)
    assert triaged["comments"] == []
    assert triaged["comment_count"] == 7
    assert triaged["comments_truncated"] is True
    assert "audit_digest" not in triaged
    assert len(triaged["triage_digest"]) == 64

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"ok":true}'

    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    with patch.object(sys.modules[__name__], "urlopen", fake_urlopen):
        client = GitHubClient("do-not-print-this")
        assert client.request("GET", "/test") == {"ok": True}
    request = captured["request"]
    assert request.headers["Authorization"] == "Bearer do-not-print-this"
    assert "do-not-print-this" not in request.full_url
    assert captured["timeout"] == HTTP_TIMEOUT_S
    print("github_issues self-test: PASS")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("list-open")
    search = subparsers.add_parser("search-open")
    search.add_argument("query")
    view = subparsers.add_parser("view")
    view.add_argument("number", type=int)
    report = subparsers.add_parser("report-bug")
    report.add_argument("--title-file", required=True, type=Path)
    report.add_argument("--body-file", required=True, type=Path)
    close = subparsers.add_parser("close")
    close.add_argument("number", type=int)
    close.add_argument("--expected-digest", required=True)
    close.add_argument("--commit", required=True)
    close.add_argument("--comment-file", required=True, type=Path)
    ledger_list = subparsers.add_parser("ledger-list")
    ledger_list.add_argument("--ledger-file", required=True, type=Path)
    ledger_add_cmd = subparsers.add_parser("ledger-add")
    ledger_add_cmd.add_argument("--ledger-file", required=True, type=Path)
    ledger_add_cmd.add_argument("--number", required=True, type=int)
    ledger_add_cmd.add_argument("--title", required=True)
    ledger_add_cmd.add_argument("--url", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_test:
        return self_test()
    if args.command is None:
        print(
            "github_issues: choose list-open, search-open, view, report-bug, close, "
            "ledger-list, ledger-add, or --self-test",
            file=sys.stderr,
        )
        return 2
    number = getattr(args, "number", None)
    if number is not None and number <= 0:
        print("github_issues: issue number must be positive", file=sys.stderr)
        return 2
    if getattr(args, "ledger_file", None) is None and args.command in ("ledger-list", "ledger-add"):
        print("github_issues: --ledger-file is required", file=sys.stderr)
        return 2

    if args.command == "ledger-list":
        try:
            entries = load_ledger(args.ledger_file)
        except GitHubError as error:
            print(f"github_issues: {error}", file=sys.stderr)
            return 2
        print(json.dumps({"ledger": str(args.ledger_file), "entries": entries}, indent=2))
        return 0
    if args.command == "ledger-add":
        try:
            result = ledger_add(args.ledger_file, args.number, args.title, args.url)
        except GitHubError as error:
            print(f"github_issues: {error}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    try:
        title = body = comment = None
        if args.command == "search-open":
            validate_public_text(args.query, "search query")
        elif args.command == "report-bug":
            title = args.title_file.read_text(encoding="utf-8").strip()
            body = args.body_file.read_text(encoding="utf-8")
            validate_public_text(title, "bug title")
            validate_public_text(body, "bug report")
        elif args.command == "close":
            if not DIGEST_RE.fullmatch(args.expected_digest):
                raise GitHubError(
                    "expected audit digest must be 64 lowercase hexadecimal characters"
                )
            comment = args.comment_file.read_text(encoding="utf-8")
            validate_public_text(comment, "closing comment")
            if args.commit not in comment:
                raise GitHubError("closing comment must cite the pushed commit")
            marker_for(number, args.commit)

        client = GitHubClient(load_token())
        if args.command == "list-open":
            result = {"repository": REPOSITORY, "issues": client.list_open()}
        elif args.command == "search-open":
            result = {"repository": REPOSITORY, "issues": client.search_open(args.query)}
        elif args.command == "view":
            result = client.issue(number)
        elif args.command == "report-bug":
            result = client.create_issue(title, body)
        else:
            result = close_issue(
                client,
                number,
                args.expected_digest,
                args.commit,
                comment,
            )
    except (GitHubError, OSError, UnicodeError) as error:
        print(f"github_issues: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
