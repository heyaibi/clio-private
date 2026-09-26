#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Tests for phase-driver notification formatting."""

from __future__ import annotations

import unittest

from scripts.pipeline.phase_notifications import (
    display_title,
    format_notification,
    phase_label,
)


class PhaseNotificationTests(unittest.TestCase):
    def test_title_preserves_common_capitalizations(self) -> None:
        self.assertEqual(
            phase_label("phase-100520-scale-ceilings-docs.md"),
            "Phase 100520 (Scale Ceilings Docs)",
        )
        self.assertEqual(
            phase_label("phase-100364-mcp-http-auto-bind-port-scan.md"),
            "Phase 100364 (MCP HTTP Auto Bind Port Scan)",
        )
        self.assertEqual(
            display_title("full-cli-confirmed-memory-mutations"),
            "Full CLI Confirmed Memory Mutations",
        )

    def test_started_and_completed_are_short_updates(self) -> None:
        phase = "phase-100520-scale-ceilings-docs.md"
        self.assertEqual(
            format_notification(phase, "started"),
            "Phase 100520 (Scale Ceilings Docs) has started.",
        )
        self.assertEqual(
            format_notification(phase, "completed"),
            "Phase 100520 (Scale Ceilings Docs) has completed.",
        )

    def test_interrupted_reason_is_brief_and_redacted(self) -> None:
        message = format_notification(
            "phase-100520-scale-ceilings-docs.md",
            "interrupted",
            reason="the operator stopped the run\nTraceback: hidden",
        )
        self.assertIn("was interrupted because the operator stopped the run.", message)
        self.assertNotIn("Traceback", message)
        self.assertIn("resume on the next driver tick", message)

        secret_message = format_notification(
            "phase-100520-scale-ceilings-docs.md",
            "interrupted",
            reason="token=secret-value",
        )
        self.assertNotIn("secret-value", secret_message)

    def test_stopped_includes_exit_code_and_run_command(self) -> None:
        message = format_notification(
            "phase-100520-scale-ceilings-docs.md",
            "stopped",
            exit_code=2,
        )
        self.assertIn("Phase 100520 (Scale Ceilings Docs) stopped.", message)
        self.assertIn("exit code 2", message)
        self.assertIn(
            "ls -la private/clio-private/runs/phase-100520/",
            message,
        )

    def test_stalled_uses_friendly_duration(self) -> None:
        message = format_notification(
            "phase-100520-scale-ceilings-docs.md",
            "stalled",
            quiet_minutes=45,
        )
        self.assertIn("no new output for 45 minutes", message)
        self.assertIn("session is still running", message)


if __name__ == "__main__":
    unittest.main()
