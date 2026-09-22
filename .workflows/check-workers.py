#!/usr/bin/env python3
"""Static contract check for birth-die workers.

Stages reference workers by exact relative path (e.g.
.workflows/workers/review-worker.md). The runner never loads workers/,
so this script is the static catch: every referenced worker must exist
and must carry its slot headings. Run after any stage/worker edit from the
repo root:
python3 private/clio-private/.workflows/check-workers.py
(root symlink python3 .workflows/check-workers.py also works;
see runner.md, Worker contract).
"""
import re
import sys
from pathlib import Path

# This file lives at private/clio-private/.workflows/check-workers.py, so
# parents[1] is the private root. resolve() follows the root symlink to the
# same physical location, so both call sites agree.
PRIV_ROOT = Path(__file__).resolve().parents[1]
REPO = PRIV_ROOT
STAGES = sorted((REPO / ".workflows" / "stages").glob("*.md"))
REF_RE = re.compile(r"\.workflows/workers/([A-Za-z0-9_.\-]+\.md)")
REQUIRED_HEADINGS = ("## You own", "## Report back")

errors = []
refs = set()
for stage in STAGES:
    for name in REF_RE.findall(stage.read_text()):
        refs.add(name)
        fp = REPO / ".workflows" / "workers" / name
        if not fp.is_file():
            errors.append(f"{stage.name} references missing worker {name}")
            continue
        text = fp.read_text()
        for heading in REQUIRED_HEADINGS:
            if heading not in text:
                errors.append(f"worker {name} lacks slot heading {heading!r}")

if not refs:
    errors.append("no worker references found in stages (check REF_RE)")

for name in sorted(refs):
    print(f"worker ok: {name}")
if errors:
    print("WORKER CHECK FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print(f"worker check passed: {len(refs)} workers referenced, all present with slots")
