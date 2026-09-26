#!/usr/bin/env bash
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
#
# Idle window content for the persistent tmux session.
#
# Run as the idle window's command by scripts/phase-tmux.sh. It is the only
# thing standing between a quiet line and a dead session: a window whose command
# exits closes, and if it is the last window the session and possibly the whole
# tmux server go with it. So this script loops forever and never exits, even
# when every file it reads is missing.
#
# Shows, in order:
#   - a HALTED banner with the reason when the line is halted (Q2: the title
#     also carries it, because a TV may not display a titlebar at all)
#   - a status block: current phase, last result, time since last activity
#   - the tail of the driver log
#
# Reads only. It writes nothing and starts nothing, so it cannot perturb a run.

set -uo pipefail

# This file lives at <repo>/private/clio-private/scripts/, so the repo root is
# three levels up, not two. Mirrors the resolution in phase-driver.sh.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PRIV="private/clio-private"
RUN_DIR="${DRIVER_RUN_DIR:-$REPO/$PRIV/runs/.driver}"
LOG="$RUN_DIR/driver.log"
HALT="$RUN_DIR/halted"
CURRENT="$RUN_DIR/current"
STALL="$RUN_DIR/stalled"
# The idle window is created by phase-tmux.sh inside a session it already
# knows the name of, so SESSION_NAME is inherited from that environment. The
# fallback only applies when the script is run by hand.
SESSION="${SESSION_NAME:-${CLIO_TMUX_SESSION:-development}}"
REFRESH="${IDLE_REFRESH_SEC:-15}"

# Longest run we will show. Keeps a long log from scrolling the banner away.
TAIL_LINES=15

human_age() {
  local secs="$1"
  [ "$secs" -ge 0 ] 2>/dev/null || secs=0
  if [ "$secs" -lt 60 ]; then printf '%ds ago' "$secs"
  elif [ "$secs" -lt 3600 ]; then printf '%dm ago' "$((secs / 60))"
  elif [ "$secs" -lt 86400 ]; then printf '%dh ago' "$((secs / 3600))"
  else printf '%dd ago' "$((secs / 86400))"
  fi
}

file_age() {
  local f="$1" now mtime=''
  [ -f "$f" ] || { printf 'never'; return 0; }
  # Pick the form for THIS platform first, then use only that one. Chaining
  # them with `stat -f %m ... || stat -c %Y ...` is wrong: on GNU coreutils
  # `stat -f` means --file-system, so `%m` is read as a device name, the
  # command prints nothing and still exits 0, the `||` fallback never runs, and
  # $mtime ends up empty. An empty value then breaks the arithmetic below.
  # BSD/macOS uses -f %m; GNU/Linux uses -c %Y.
  if stat -c %Y "$f" >/dev/null 2>&1; then
    mtime="$(stat -c %Y "$f" 2>/dev/null)"
  else
    mtime="$(stat -f %m "$f" 2>/dev/null)"
  fi
  # Never do arithmetic on an unchecked value.
  case "$mtime" in
    ''|*[!0-9]*) mtime=0 ;;
  esac
  now="$(date +%s)"
  human_age "$((now - mtime))"
}

last_result() {
  local line
  line="$(grep -E 'completed|HALTED|blocked|rejected' "$LOG" 2>/dev/null \
    | grep -v 'notify' | tail -1)"
  [ -n "$line" ] && printf '%s' "${line#* }" || printf 'no run recorded yet'
}

# The whole body is guarded: a missing file, an unreadable one, or a grep that
# matches nothing must all still produce a screen and loop again.
draw() {
  local cur banner
  clear 2>/dev/null || printf '\033[H\033[2J'
  printf '\033[1mclio unattended line\033[0m   session: %s\n\n' "$SESSION"

  if [ -f "$HALT" ]; then
    # Big banner first. This is the case a TV must never miss, and the title
    # alone is not enough because the titlebar may not be visible.
    printf '\033[1;41;97m  HALTED  \033[0m  %s\n\n' "$(date '+%Y-%m-%d %H:%M:%S')"
    printf '  reason: '
    tr '\n' ' ' <"$HALT" 2>/dev/null | cut -c1-100
    printf '\n\n'
  else
    printf '\033[1;32m  RUNNING\033[0m  (no halt marker)\n\n'
  fi

  cur="$(cat "$CURRENT" 2>/dev/null || true)"
  printf '  %-14s %s\n' 'phase now:' "${cur:-none}"
  printf '  %-14s %s\n' 'last result:' "$(last_result)"
  printf '  %-14s %s\n' 'last log:' "$(file_age "$LOG")"
  if [ -f "$STALL" ]; then
    printf '  %-14s %s\n' 'stalled:' "$(tr '\n' ' ' <"$STALL" 2>/dev/null | cut -c1-60)"
  fi

  printf '\n  ---- driver log (last %s lines) ----\n' "$TAIL_LINES"
  tail -n "$TAIL_LINES" "$LOG" 2>/dev/null || printf '  (no log yet at %s)\n' "$LOG"
  printf '\n'
}

# Loop forever. `draw` is allowed to fail; the sleep keeps the window alive
# either way, which is the property that protects the session.
while :; do
  draw || true
  sleep "$REFRESH" || sleep 5
done
