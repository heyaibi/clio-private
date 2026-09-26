#!/usr/bin/env python3
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
"""Shared phase-number policy for the private roadmap pipeline.

Phase numbers at or above ``PARKED_PHASE_FLOOR`` are roadmap-only artifacts.
They stay visible in the roadmap and index for planning, but the pipeline
selector never picks them and the runner refuses to launch them.
"""

PARKED_PHASE_FLOOR = 900000


def is_runnable_phase(number):
    """True when ``number`` may be selected or launched by the pipeline."""
    return int(number) < PARKED_PHASE_FLOOR
