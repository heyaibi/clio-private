#!/usr/bin/env bash
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
#
# Stage-title hook: rename the phase window as each glide stage starts.
#
# Wired into workflow/pipelines/default.yaml as the `pre_step` hook. glide
# already calls that point with the step id (glide/src/glide/router.py:121) and
# already passes context as GLIDE_* environment variables
# (glide/src/glide/hookrun.py:105), so this needs no change to glide.
#
# WHY THIS MUST ALWAYS EXIT 0
# `pre_step` is a GATING lifecycle point (glide/src/glide/hooks.py:47). A
# nonzero exit from this script does not warn, it STOPS THE RUN, and the phase
# halts. A transient tmux failure, a missing session, or a missing binary must
# therefore never propagate. Every path below returns 0. If you edit this file,
# keep that property: `exit 0` is the last line for a reason.
#
# Reads GLIDE_STEP and CLIO_TMUX_SESSION. Writes only tmux window state.

set -uo pipefail

# The five step ids in the pipeline. A `case` over fixed ids is used rather than
# reading the stage files' `name:` frontmatter, because a missing or malformed
# stage file would then degrade the title, where a `case` cannot.
stage_label() {
  case "${1:-}" in
    developer)  printf 'implement' ;;
    adversary)  printf 'adversary' ;;
    remediator) printf 'remedy' ;;
    approver)   printf 'check-remedy' ;;
    finalize)   printf 'finalize' ;;
    *)          printf '%s' "${1:-unknown}" ;;
  esac
}

# The phase number. glide does not pass it: `pre_step` carries run_dir, run_id,
# pipeline, step, attempt, and harness only. The driver exports
# CLIO_PHASE_NUMBER into the launch environment, which the hook inherits, and
# the run_dir fallback covers a run started without that export.
phase_number() {
  if [ -n "${CLIO_PHASE_NUMBER:-}" ]; then printf '%s' "$CLIO_PHASE_NUMBER"; return 0; fi
  local base
  base="$(basename "${GLIDE_RUN_DIR:-}" 2>/dev/null)"
  case "$base" in
    phase-*) printf '%s' "${base#phase-}" ;;
    *)       printf '?' ;;
  esac
}

main() {
  local step label window title session number
  step="${GLIDE_STEP:-}"
  session="${CLIO_TMUX_SESSION:-${SESSION_NAME:-development}}"

  # Nothing to say without a step, and nothing to say without tmux.
  [ -n "$step" ] || return 0
  command -v tmux >/dev/null 2>&1 || return 0
  tmux has-session -t "$session" 2>/dev/null || return 0

  label="$(stage_label "$step")"
  number="$(phase_number)"
  window="$session:phase"
  # A literal title, not a format: set-titles-string is session-scoped, and a
  # format would follow whichever window the attached client is viewing.
  title="phase $number $label"

  # Best effort. Both may fail (window gone, session killed); neither is fatal.
  tmux rename-window -t "$window" "phase $label" 2>/dev/null || true
  tmux set-option -t "$session" set-titles-string "$title" 2>/dev/null || true
  return 0
}

main || true
exit 0
