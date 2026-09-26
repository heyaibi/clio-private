#!/usr/bin/env bash
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
#
# Clio unattended phase driver.
#
# Canonical layout: this script lives at
# private/clio-private/scripts/phase-driver.sh in the nested private repo.
# Every invocation below runs with the repo root as cwd. Call from the
# root, e.g.:
#   bash private/clio-private/scripts/phase-driver.sh --check
#
#   phase-driver.sh [--dry-run]                  # cron entrypoint
#   phase-driver.sh --check                      # report environment readiness
#   phase-driver.sh --self-test                  # hermetic guard/halt/notify test
#   phase-driver.sh --stop                       # stop the live run (halt + Ctrl-C)
#   phase-driver.sh --session <N> <phase-file>   # one phase, run inside tmux
#
# The server reserves the selected phase in the private coordination branch
# before tmux starts. A coordination fetch/push failure is fail-closed.
#
# Cron runs the driver every few minutes. It does nothing while a phase is
# running or while the line is halted; otherwise it starts the lowest
# uncompleted phase in the tmux session named below. A phase that ends
# blocked/rejected/errored, OR that is stopped by a signal (Ctrl-C / tmux
# kill-session), writes a halt marker and stops the line until the operator
# clears it. Start/end/halt notifications go to Discord through the Hermes
# profile below.
#
# Optional untracked overrides live in
# private/clio-private/runs/.driver.env (sourced if present):
# HERMES_PROFILE_NAME, DISCORD_CHANNEL, DISCORD_FALLBACK_CHANNEL,
# HEARTBEAT_URL, STALE_AFTER_SEC, LOG_KEEP_DAYS, TMUX_WIDTH, TMUX_HEIGHT,
# PHASE_MACHINE_ID, PHASE_COORDINATION_BRANCH.
#
# The tmux session is persistent: it is created once and outlives every phase.
# It holds an `idle` window (status, created once) and a `phase` window (created
# per launch, closes itself when the phase ends). "Busy" therefore means the
# phase window exists, NOT that the session exists. Attach a display with
# `tmux attach -t development -r`; -r is read-only and ignores the client's
# size, so the display cannot resize the agent's pane.
#
# All tmux window handling lives in scripts/phase-tmux.sh.
#
# Local test hooks (never set these in cron):
#   DISABLE_NOTIFY=1      log notifications instead of sending them
#   DISABLE_DISCORD=1     alias for disabling Discord sends (same effect today)
#   DRIVER_STUB_RC=<n>    skip glide; pretend it exited with rc <n>
#   DRIVER_STUB_SLEEP=<s> how long the stub "works" (default 2)
#   DRIVER_RUN_DIR=<dir>  isolate runtime state (used by --self-test)
set -euo pipefail

# Resolve the repo root from this script's location. Falls back to git
# when the layout is unexpected.
_SCRIPT_SRC="${BASH_SOURCE[0]}"
while [ -L "$_SCRIPT_SRC" ]; do
  _SCRIPT_SRC="$(readlink "$_SCRIPT_SRC")"
  case "$_SCRIPT_SRC" in
    /*) : ;;
    *) _SCRIPT_SRC="$(dirname "${BASH_SOURCE[0]}")/$_SCRIPT_SRC" ;;
  esac
done
_SCRIPT_DIR="$(cd "$(dirname "$_SCRIPT_SRC")" && pwd)"
if [ "$(basename "$_SCRIPT_DIR")" = "scripts" ] \
  && [ "$(basename "$(dirname "$_SCRIPT_DIR")")" = "clio-private" ]; then
  REPO="$(cd "$_SCRIPT_DIR/../../.." && pwd)"
else
  REPO="$(cd "$_SCRIPT_DIR/.." && pwd)"
fi
unset _SCRIPT_SRC _SCRIPT_DIR
if [ ! -f "$REPO/Cargo.toml" ] && command -v git >/dev/null 2>&1; then
  _GIT_ROOT="$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "${_GIT_ROOT:-}" ] && REPO="$_GIT_ROOT"
  unset _GIT_ROOT
fi

# Canonical private locations (all invoked with $REPO as cwd).
PRIV="private/clio-private"
WF="$REPO/$PRIV/runs"
SCRIPTS="$REPO/$PRIV/scripts"
NOTIFIER="$SCRIPTS/pipeline/phase_notifications.py"

# Optional untracked overrides; keep secrets/ids out of the committed file.
# shellcheck disable=SC1091
[ -f "$WF/.driver.env" ] && . "$WF/.driver.env"

: "${HERMES_PROFILE_NAME:=not-james-gosling}"
: "${DISCORD_CHANNEL:=1546601332276727828}"
: "${DISCORD_FALLBACK_CHANNEL:=}"
: "${HEARTBEAT_URL:=}"
: "${STALE_AFTER_SEC:=2700}"
: "${LOG_KEEP_DAYS:=7}"
: "${DRIVER_RUN_DIR:=$WF/.driver}"
: "${SESSION_NAME:=development}"
: "${TMUX_WIDTH:=164}"
: "${TMUX_HEIGHT:=56}"
: "${PHASE_MACHINE_ID:=${CLIO_MACHINE_ID:-server-01}}"
: "${PHASE_COORDINATION_BRANCH:=${CLIO_PHASE_COORDINATION_BRANCH:-master}}"
# When set to 1, the driver takes back a phase whose blocking claim is this
# host's own, instead of logging WAIT_FOR_CLAIM and stopping the line. That
# state is what a crashed, stopped, or blocked run of our own phase leaves
# behind, and it is recoverable; a claim held by *another* host is never
# touched, and coordination still fences both cases. Default 0 keeps the
# fail-closed behaviour: recover deliberately, not by accident.
: "${PHASE_RECOVER_OWN_CLAIM:=0}"
export CLIO_MACHINE_ID="$PHASE_MACHINE_ID"
export CLIO_PHASE_COORDINATION_BRANCH="$PHASE_COORDINATION_BRANCH"

PIPELINE="private/clio-private/workflow/pipelines/default.yaml"
# SESSION_NAME may also arrive from the environment, which is how a launched
# phase window learns which session it belongs to. The parent's own name wins
# for the cron process; the child gets SESSION_NAME exported in its launch
# environment, so prefer that when this process is itself a phase run.
if [ -n "${SESSION_NAME:-}" ] && [ -n "${CLIO_TMUX_SESSION:-}" ]; then
  SESSION="$CLIO_TMUX_SESSION"
elif [ -n "${SESSION_NAME:-}" ]; then
  SESSION="$SESSION_NAME"
else
  SESSION="development"
fi
SESSION_NAME="$SESSION"
PROFILE="$HERMES_PROFILE_NAME"
CHANNEL="$DISCORD_CHANNEL"
FALLBACK="$DISCORD_FALLBACK_CHANNEL"
RUN_DIR="$DRIVER_RUN_DIR"
LOCK="$RUN_DIR/driver.lock"
HALT="$RUN_DIR/halted"
STALL="$RUN_DIR/stalled"
CURRENT="$RUN_DIR/current"
PIDFILE="$RUN_DIR/pid"
NOTIFY_BROKEN="$RUN_DIR/notify-broken"
LOG="$RUN_DIR/driver.log"

# Persistent tmux session: idle + phase windows. Sourced after the paths above
# are defined because the helper uses SCRIPTS, LOG, and REPO at call time.
# shellcheck disable=SC1091
. "$SCRIPTS/phase-tmux.sh"

DRY_RUN=0
CUR_PHASE=""
CUR_PHASE_FILE=""
_STOPPED=0
NOTIFY_DEAD=0

# cron gives a minimal PATH; add common locations as FALLBACKS (append, never
# shadow). A pyenv/conda python3 earlier in PATH must keep winning, because a
# homebrew python3 may lack PyYAML and crash runner.py on import.
export PATH="${PATH:-/usr/bin:/bin}:/usr/bin:/bin:$HOME/.local/bin:$HOME/homebrew/bin:/opt/homebrew/bin:/usr/local/bin"

# Pick a python3 that can actually run runner.py (needs PyYAML), by absolute
# path so the choice survives into the tmux session regardless of its PATH.
PYTHON=""
resolve_python() {
  local cand
  for cand in "${PYTHON:-}" "$(command -v python3 2>/dev/null)" \
              "$HOME/.pyenv/shims/python3" /opt/homebrew/bin/python3 \
              /usr/local/bin/python3 /usr/bin/python3; do
    [ -n "$cand" ] && [ -x "$cand" ] || continue
    if "$cand" -c 'import yaml' >/dev/null 2>&1; then PYTHON="$cand"; return 0; fi
  done
  return 1
}

ts() { date +%Y-%m-%dT%H:%M:%S%z; }

log() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '%s %s\n' "$(ts)" "$*"
  else
    printf '%s %s\n' "$(ts)" "$*" >>"$LOG"
  fi
}

# log, and also speak on stdout so a manual run is not silent (cron captures it).
say() { log "$*"; [ "$DRY_RUN" = 1 ] && return 0; printf '%s\n' "$*"; }

resolve_python || PYTHON="python3"

# Best-effort send: bounded by a timeout (when available) and with stdin
# closed, so a hung or interactive hermes can never stall the run.
send_one() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 20 hermes -p "$PROFILE" send --to "$1" "$2" </dev/null >>"$LOG" 2>&1
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout 20 hermes -p "$PROFILE" send --to "$1" "$2" </dev/null >>"$LOG" 2>&1
  else
    hermes -p "$PROFILE" send --to "$1" "$2" </dev/null >>"$LOG" 2>&1
  fi
}

# Notifications are strictly best-effort: a missing profile, a dead Discord or a
# hung hermes must never block or halt the pipeline. On total failure the channel
# is marked dead for this process, so we stop retrying and stop spamming.
notify() {
  local msg="$1" target="discord:$CHANNEL"
  if [ "$NOTIFY_DEAD" = 1 ]; then
    log "notify skipped (channel unavailable): $msg"
    return 0
  fi
  if [ -n "${DISABLE_NOTIFY:-}" ] || [ -n "${DISABLE_DISCORD:-}" ]; then
    log "notify (disabled): $msg"
    return 0
  fi
  if ! command -v hermes >/dev/null 2>&1; then
    log "notify skipped (hermes not on PATH): $msg"
    return 0
  fi
  if send_one "$target" "$msg"; then
    log "notify ok: $msg"; rm -f "$NOTIFY_BROKEN"; return 0
  fi
  sleep 2
  if send_one "$target" "$msg"; then
    log "notify ok (retry): $msg"; rm -f "$NOTIFY_BROKEN"; return 0
  fi
  if [ -n "$FALLBACK" ] && send_one "discord:$FALLBACK" "$msg"; then
    log "notify via fallback channel: $msg"; return 0
  fi
  printf 'notify broken at %s: %s\n' "$(ts)" "$msg" >"$NOTIFY_BROKEN"
  NOTIFY_DEAD=1
  log "notify FAILED (wrote $NOTIFY_BROKEN); further sends skipped this run: $msg"
}

notify_phase() {
  local phase_file="$1" event="$2" reason="${3:-}" exit_code="${4:-}"
  local quiet_minutes="${5:-45}" message phase_number
  local args=(--phase-file "$phase_file" --event "$event" --quiet-minutes "$quiet_minutes")
  [ -n "$reason" ] && args+=(--reason "$reason")
  [ -n "$exit_code" ] && args+=(--exit-code "$exit_code")
  message="$("$PYTHON" "$NOTIFIER" "${args[@]}" 2>/dev/null || true)"
  if [ -n "$message" ]; then
    notify "$message"
    return 0
  fi
  phase_number="${phase_file##*/phase-}"
  phase_number="${phase_number%%-*}"
  notify "Phase ${phase_number:-unknown} needs attention."
}

phase_state() {
  local file="$WF/phase-$(printf '%06d' "$1")/run.json"
  "$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("state",""))' \
    "$file" 2>/dev/null || true
}

# A signal-driven stop must halt and notify: bash dies before any trailing
# code after a signal, so the work is done in a trap, marker first. (Ctrl-C
# reaches this; tmux kill-session does NOT signal the pane, which is why the
# driver also records the session PID and treats a live PID with no session
# as an orphan.)
on_stop() {
  local rc="$1"
  [ "$_STOPPED" = 1 ] && exit "$rc"
  _STOPPED=1
  if [ -n "$CUR_PHASE" ]; then
    printf 'phase %s stopped by signal (rc=%s) at %s\n' \
      "$CUR_PHASE" "$rc" "$(ts)" >"$HALT"
    notify_phase "$CUR_PHASE_FILE" stopped-signal
  fi
  rm -f "$CURRENT" "$PIDFILE"
  exit "$rc"
}

run_session() {
  local number="$1" rel="$2" rc=0 state
  CUR_PHASE="$number"
  CUR_PHASE_FILE="$rel"
  mkdir -p "$RUN_DIR"
  trap 'on_stop 129' HUP
  trap 'on_stop 130' INT
  trap 'on_stop 143' TERM
  printf '%s\n' "$$" >"$PIDFILE"
  cd "$REPO"
  export CLIO_MACHINE_ID="${CLIO_MACHINE_ID:-$PHASE_MACHINE_ID}"
  tmux_set_title "phase $number running"
  notify_phase "$rel" started
  if [ -n "${DRIVER_STUB_RC:-}" ]; then
    log "STUB mode: simulating glide (rc=$DRIVER_STUB_RC)"
    sleep "${DRIVER_STUB_SLEEP:-2}"
    rc="$DRIVER_STUB_RC"
  else
    PYTHONPATH="$REPO/private/clio-private/glide/src" "$PYTHON" -m glide run --pipeline "$PIPELINE" \
      --input "phase_number=$number" --input "phase_file=$rel" || rc=$?
  fi
  state="$(phase_state "$number")"
  case "$rc" in
    0)   tmux_set_title "phase $number done"
         notify_phase "$rel" completed ;;
    3)   : ;;
    130) tmux_set_title "HALTED phase $number (interrupted)"
         notify_phase "$rel" interrupted "the process received an interrupt signal" ;;
    *)   printf 'phase %s rc=%s state=%s at %s\n' \
           "$number" "$rc" "${state:-unknown}" "$(ts)" >"$HALT"
          # The title is set before the window closes, so the halt survives the
          # phase window going away and the idle display taking over.
          tmux_set_title "HALTED phase $number (rc=$rc)"
          notify_phase "$rel" stopped "" "$rc" ;;
  esac
  rm -f "$CURRENT" "$PIDFILE"
  exit "$rc"
}

# Busy means "a phase window is running", not "the session exists". The session
# is persistent and always exists once created, so testing it would block the
# line forever. A dead-but-retained phase window is reclaimed, never the
# session, so a display attached to the idle window is not disturbed.
tmux_busy() {
  tmux_phase_window_alive && return 0
  if tmux_window_exists; then
    log "stale dead phase window in '$SESSION'; reclaiming it"
    tmux_phase_window_close
  fi
  return 1
}

newest_mtime() {
  local newest=0 f m
  for f in "$@"; do
    [ -f "$f" ] || continue
    m="$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null || echo 0)"
    [ "$m" -gt "$newest" ] && newest="$m"
  done
  printf '%s\n' "$newest"
}

# While a session is live, alert once if its output has gone quiet too long.
check_stall() {
  [ -f "$STALL" ] && return 0
  local n phase_dir newest now age phase_file
  n="$(cat "$CURRENT" 2>/dev/null || true)"
  [ -n "$n" ] || return 0
  phase_dir="$WF/phase-$(printf '%06d' "$n")"
  newest="$(newest_mtime "$RUN_DIR/session-$n.log" "$phase_dir"/*)"
  [ "$newest" -gt 0 ] || return 0
  now="$(date +%s)"; age=$((now - newest))
  if [ "$age" -gt "$STALE_AFTER_SEC" ]; then
    printf 'stalled: phase %s no output for %ss at %s\n' \
      "$n" "$age" "$(ts)" >"$STALL"
    phase_file="$(find "$REPO/$PRIV/roadmap" -maxdepth 1 -type f \
      -name "phase-$(printf '%06d' "$n")-*.md" -print -quit)"
    if [ -n "$phase_file" ]; then
      notify_phase "$phase_file" stalled "" "" "$((STALE_AFTER_SEC / 60))"
    else
      notify "Phase $n looks stalled.

There has been no new output for $STALE_AFTER_SEC seconds. The session is still running; inspect it before stopping the work."
    fi
  fi
}

prune() {
  [ "$DRY_RUN" = 1 ] && return 0
  find "$RUN_DIR" -maxdepth 1 -name 'session-*.log' -mtime "+$LOG_KEEP_DAYS" \
    -delete 2>/dev/null || true
}

heartbeat() {
  [ -n "$HEARTBEAT_URL" ] || return 0
  curl -fsS -m 10 --retry 3 "$HEARTBEAT_URL" >/dev/null 2>&1 \
    || log "heartbeat ping failed ($HEARTBEAT_URL)"
}

coordination_select() {
  # The JSON result is deliberately consumed instead of parsing the legacy
  # tab output. A failed fetch/push must never turn into an unclaimed launch.
  "$PYTHON" "$SCRIPTS/pipeline/next_phase.py" --repo "$REPO" --server \
    --machine-id "$PHASE_MACHINE_ID" --json "$@"
}

selection_value() {
  local key="$1"
  "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' \
    "$key"
}

_drive() {
  cd "$REPO"

  if [ "$DRY_RUN" = 1 ]; then
    [ -f "$HALT" ] && { log "dry-run: halted; would refuse to advance"; return 0; }
    tmux_phase_window_alive 2>/dev/null \
      && { log "dry-run: phase window is running; would skip"; return 0; }
    local selection selection_rc=0 state
    selection="$(coordination_select --read-only)" || selection_rc=$?
    if [ "$selection_rc" -ne 0 ] && [ "$selection_rc" -ne 1 ] \
        && [ "$selection_rc" -ne 2 ] && [ "$selection_rc" -ne 3 ]; then
      log "dry-run: coordination unavailable; refusing to launch"
      return 0
    fi
    state="$(printf '%s' "$selection" | selection_value state)"
    case "$state" in
      AVAILABLE)
        local number rel
        number="$(printf '%s' "$selection" | selection_value phase)"
        rel="$(printf '%s' "$selection" | selection_value path)"
        log "dry-run: would reserve and launch phase $number in tmux '$SESSION'"
        printf 'would launch: tmux new-window -d -t %s -n phase -c %s "bash %s/private/clio-private/scripts/phase-driver.sh --session %s %s"\n' \
          "$SESSION" "$REPO" "$REPO" "$number" "$rel"
        ;;
      WAIT_FOR_CLAIM)
        wait_phase="$(printf '%s' "$selection" | selection_value phase)"
        wait_owner="$(printf '%s' "$selection" | selection_value owner)"
        if [ "$PHASE_RECOVER_OWN_CLAIM" = 1 ] \
            && [ "$wait_owner" = "$PHASE_MACHINE_ID" ] \
            && [ "$wait_phase" != "" ]; then
          log "dry-run: would recover this host's own claim on phase $wait_phase and launch it"
        else
          log "dry-run: WAIT_FOR_CLAIM (phase $wait_phase, owner $wait_owner); no launch"
        fi
        ;;
      COORDINATION_INCONSISTENT)
        log "dry-run: coordination state conflicts with completion evidence; no launch"
        ;;
      NO_PHASE)
        log "dry-run: no uncompleted phase"
        ;;
      *)
        log "dry-run: unexpected coordination result '$state'; no launch"
        ;;
    esac
    return 0
  fi

  mkdir -p "$RUN_DIR"

  if [ -f "$HALT" ]; then
    log "halted ($(tr '\n' ' ' <"$HALT")); refusing to advance"
    return 0
  fi

  if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK"
    flock -n 9 || { log "another driver instance holds the lock; skip"; return 0; }
  fi

  if tmux_busy; then
    check_stall
    log "phase window is running; skip"
    return 0
  fi

  # No phase window, but a recorded live PID means an orphaned run (e.g. after
  # `tmux kill-window`, which does not signal the pane). The session itself
  # outlives every phase, so it proves nothing. Halt rather than start a
  # second, concurrent run.
  if [ -f "$PIDFILE" ]; then
    local opid
    opid="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [ -n "$opid" ] && kill -0 "$opid" 2>/dev/null; then
      log "orphaned run detected (pid $opid, no phase window); halting"
      [ -f "$HALT" ] || printf 'orphaned run pid %s at %s\n' "$opid" "$(ts)" >"$HALT"
      notify "a phase run (pid $opid) is alive but its tmux phase window is gone (orphaned). Line stopped; investigate."
      return 0
    fi
    rm -f "$PIDFILE"
  fi

  # No live phase: clear per-session state a hard kill may have left behind.
  rm -f "$CURRENT" "$STALL"
  prune
  # Keep the display truthful between phases. A halted line says so here too, so
  # the reason is visible even if the titlebar is not rendered.
  if [ -f "$HALT" ]; then
    tmux_set_title "HALTED - $(tr '\n' ' ' <"$HALT" | cut -c1-60)"
  else
    tmux_set_title "idle - waiting for next phase"
  fi

  local out rc=0 number rel reservation_id reservation_generation
  if [ "${1:-}" = "--self-test" ]; then
    out="$("$PYTHON" "$SCRIPTS/pipeline/next_phase.py" --repo "$REPO")" || rc=$?
    if [ "$rc" -ne 0 ]; then
      log "no uncompleted phase (next_phase rc=$rc)"
      return 0
    fi
    number="${out%%$'\t'*}"; rel="${out#*$'\t'}"
    reservation_id=""; reservation_generation=""
  else
    if ! "$PYTHON" "$SCRIPTS/pipeline/gitsync.py" --root "$REPO" --mode start \
        >"$RUN_DIR/coordination-sync.json" 2>/dev/null; then
      log "coordination checkout sync failed; refusing to launch (see $RUN_DIR/coordination-sync.json)"
      return 1
    fi
    local selection selection_rc=0 selection_state
    selection="$(coordination_select)" || selection_rc=$?
    if [ "$selection_rc" -ne 0 ] && [ "$selection_rc" -ne 2 ] \
        && [ "$selection_rc" -ne 3 ]; then
      log "coordination state unavailable; refusing to launch (next_phase rc=$selection_rc)"
      return 1
    fi
    selection_state="$(printf '%s' "$selection" | selection_value state)"
    case "$selection_state" in
      RESERVED)
        number="$(printf '%s' "$selection" | selection_value phase)"
        rel="$(printf '%s' "$selection" | selection_value path)"
        reservation_id="$(printf '%s' "$selection" | selection_value reservation_id)"
        reservation_generation="$(printf '%s' "$selection" | selection_value generation)"
        log "reserved phase $number ($rel) for $PHASE_MACHINE_ID"
        ;;
      WAIT_FOR_CLAIM)
        wait_phase="$(printf '%s' "$selection" | selection_value phase)"
        wait_owner="$(printf '%s' "$selection" | selection_value owner)"
        wait_status="$(printf '%s' "$selection" | selection_value status)"
        if [ "$PHASE_RECOVER_OWN_CLAIM" = 1 ] \
            && [ "$wait_owner" = "$PHASE_MACHINE_ID" ] \
            && [ "$wait_phase" != "" ]; then
          # Our own claim, left behind by a run that crashed, was stopped, or
          # ended blocked. Take it back explicitly so the phase can finish.
          # A claim held by any other host still stops the line.
          log "recovering own claim on phase $wait_phase (status=$wait_status) for $PHASE_MACHINE_ID"
          if "$PYTHON" "$SCRIPTS/pipeline/phase_reservations.py" takeover \
              --repo-root "$REPO" --phase "$wait_phase" \
              --machine-id "$PHASE_MACHINE_ID" \
              --expected-reservation-id "$(printf '%s' "$selection" | selection_value reservation_id)" \
              --expected-generation "$(printf '%s' "$selection" | selection_value generation)" \
              --confirm >"$RUN_DIR/claim-recovery-$wait_phase.json" 2>&1; then
            number="$wait_phase"
            rel="private/clio-private/roadmap/$(ls "$REPO/$PRIV/roadmap" 2>/dev/null | grep "^phase-$wait_phase-" | head -1)"
            log "recovered phase $number ($rel); continuing"
          else
            log "claim recovery for phase $wait_phase failed; see $RUN_DIR/claim-recovery-$wait_phase.json"
            return 1
          fi
        else
          log "WAIT_FOR_CLAIM for phase $wait_phase (owner=$wait_owner status=$wait_status); no launch"
          return 0
        fi
        ;;
      COORDINATION_INCONSISTENT)
        log "coordination state conflicts with completion evidence; no launch"
        return 1
        ;;
      NO_PHASE)
        log "no uncompleted phase"
        return 0
        ;;
      *)
        log "unexpected coordination result '$selection_state'; refusing to launch"
        return 1
        ;;
    esac
  fi
  log "next phase: $number ($rel)"

  local envs=""
  [ -z "${HERMES_PROFILE_NAME:-}" ] || envs="$envs HERMES_PROFILE_NAME='$HERMES_PROFILE_NAME'"
  [ -z "${DISCORD_CHANNEL:-}" ] || envs="$envs DISCORD_CHANNEL='$DISCORD_CHANNEL'"
  [ -z "${DISCORD_FALLBACK_CHANNEL:-}" ] || envs="$envs DISCORD_FALLBACK_CHANNEL='$DISCORD_FALLBACK_CHANNEL'"
  [ -z "${DISABLE_NOTIFY:-}" ] || envs="$envs DISABLE_NOTIFY='$DISABLE_NOTIFY'"
  [ -z "${DISABLE_DISCORD:-}" ] || envs="$envs DISABLE_DISCORD='$DISABLE_DISCORD'"
  [ -z "${DRIVER_STUB_RC:-}" ] || envs="$envs DRIVER_STUB_RC='$DRIVER_STUB_RC'"
  [ -z "${DRIVER_STUB_SLEEP:-}" ] || envs="$envs DRIVER_STUB_SLEEP='$DRIVER_STUB_SLEEP'"
  [ -z "${DRIVER_RUN_DIR:-}" ] || envs="$envs DRIVER_RUN_DIR='$DRIVER_RUN_DIR'"
  [ -z "${CLIO_MACHINE_ID:-}" ] || envs="$envs CLIO_MACHINE_ID='$CLIO_MACHINE_ID'"
  [ -z "${CLIO_PHASE_COORDINATION_BRANCH:-}" ] || envs="$envs CLIO_PHASE_COORDINATION_BRANCH='$CLIO_PHASE_COORDINATION_BRANCH'"
  [ -z "$reservation_id" ] || envs="$envs CLIO_RESERVATION_ID='$reservation_id'"
  [ -z "$reservation_generation" ] || envs="$envs CLIO_RESERVATION_GENERATION='$reservation_generation'"
  # The stage-title hook (pre_step) needs the session and the phase number; glide
  # passes neither, so both travel through the launch environment. SESSION_NAME
  # is exported too so the child driver resolves the same session name.
  envs="$envs CLIO_TMUX_SESSION='$SESSION' CLIO_PHASE_NUMBER='$number' DRIVER_RUN_DIR='$RUN_DIR' SESSION_NAME='$SESSION'"
  local launch="${envs:+$envs }bash '$REPO/$PRIV/scripts/phase-driver.sh' --session '$number' '$rel'"

  # Geometry: the session is created once at TMUX_WIDTH x TMUX_HEIGHT with
  # `window-size manual`, so it holds that size even when a smaller display
  # attaches. runner.py copies the pane size into each harness pty, so this is
  # what the agent actually works at. The phase window is then sized explicitly,
  # because new-window has no -x/-y and inherits the session size instead.
  #
  # The session is ensured first and never killed, so a display attached to the
  # idle window survives the launch. 9>&- drops the flock fd, as before.
  9>&- tmux_session_ensure \
    || { notify "phase $number failed to create tmux session '$SESSION'"; return 1; }
  # Set the title BEFORE the window opens. The child sets its own titles as it
  # runs, and anything written after the window opens races with them: a parent
  # "starting" landing after the child's "done" would leave the display showing
  # a phase that already finished.
  tmux_set_title "phase $number starting"
  9>&- tmux_phase_window_open "$launch" "$RUN_DIR/session-$number.log" \
    || { notify "phase $number failed to launch in tmux"; return 1; }
  printf '%s\n' "$number" >"$CURRENT"
  # The window stays named 'phase'. Renaming it to carry the phase number would
  # break every target string in phase-tmux.sh that looks it up by name, and
  # the phase number is already in the title and the log. The stage hook
  # renames it per stage instead, which is the display-facing label.
  tmux_phase_window_select
  log "launched phase $number in tmux '$SESSION' window 'phase'"
}

drive() {
  local rc=0
  if command -v flock >/dev/null 2>&1; then
    _drive "${1:-}" || rc=$?
  else
    mkdir -p "$RUN_DIR"
    local portable_lock="$RUN_DIR/driver.lock.d"
    if ! mkdir "$portable_lock" 2>/dev/null; then
      log "another driver instance holds the portable lock; skip"
      heartbeat
      return 0
    fi
    (
      trap 'rmdir "$portable_lock" 2>/dev/null || true' EXIT
      _drive "${1:-}" || rc=$?
      exit "$rc"
    )
    rc=$?
  fi
  heartbeat
  return "$rc"
}

stop() {
  mkdir -p "$RUN_DIR"
  printf 'stopped by operator at %s\n' "$(ts)" >"$HALT"
  # Ctrl-C must reach the phase window. Targeting the session would send it to
  # whichever window is current, which may be the idle status display.
  if tmux_phase_window_alive; then
    tmux_phase_window_interrupt
    log "stop: sent Ctrl-C to '$SESSION:phase' and wrote halt marker"
  elif tmux_session_exists; then
    log "stop: wrote halt marker (session idle, no phase window)"
  else
    log "stop: wrote halt marker (no live session)"
  fi
}

# Wait for the phase window to disappear. The session itself is persistent and
# is never waited on.
wait_phase_window_gone() {
  local i=0
  while tmux_window_exists; do
    i=$((i + 1)); [ "$i" -gt 60 ] && break
    sleep 0.25
  done
  sleep 0.3
}

driver_self_test() {
  local fail=0 tmp
  tmp="$(mktemp -d)"
  SESSION="ar-driver-selftest-$$"
  SESSION_NAME="$SESSION"
  DRIVER_RUN_DIR="$tmp/run"
  DISABLE_NOTIFY=1
  DISABLE_DISCORD=1
  DRIVER_STUB_RC=0
  # Long enough that the phase window is still open for the checks below. The
  # phase now lives in a window that closes on exit, so a 1s stub could finish
  # before the first assertion ran.
  DRIVER_STUB_SLEEP=6
  export SESSION_NAME DRIVER_RUN_DIR DISABLE_NOTIFY DISABLE_DISCORD DRIVER_STUB_RC DRIVER_STUB_SLEEP
  RUN_DIR="$DRIVER_RUN_DIR"
  LOCK="$RUN_DIR/driver.lock"; HALT="$RUN_DIR/halted"
  STALL="$RUN_DIR/stalled"; CURRENT="$RUN_DIR/current"
  PIDFILE="$RUN_DIR/pid"
  NOTIFY_BROKEN="$RUN_DIR/notify-broken"; LOG="$RUN_DIR/driver.log"
  mkdir -p "$RUN_DIR"
  echo "self-test session: $SESSION  state dir: $RUN_DIR"

  title_of() { tmux show-option -t "$SESSION" -v set-titles-string 2>/dev/null || true; }

  drive --self-test || true
  tmux_session_exists \
    && echo "ok: launched a session" || { echo "FAIL: session not created"; fail=1; }
  tmux_window_exists \
    && echo "ok: phase window opened" || { echo "FAIL: phase window not opened"; fail=1; }
  tmux list-windows -t "$SESSION" -F '#{window_name}' 2>/dev/null | grep -qx -- idle \
    && echo "ok: idle window present" || { echo "FAIL: idle window missing"; fail=1; }
  geom="$(tmux_phase_window_geometry)"
  [ "$geom" = "${TMUX_WIDTH}x${TMUX_HEIGHT}" ] \
    && echo "ok: phase window geometry $geom" \
    || { echo "FAIL: geometry ${geom:-gone}, want ${TMUX_WIDTH}x${TMUX_HEIGHT}"; fail=1; }
  case "$(title_of)" in
    *"starting"*|*"running"*) echo "ok: running title set ($(title_of))" ;;
    *) echo "FAIL: running title not set, got '$(title_of)'"; fail=1 ;;
  esac
  drive --self-test || true
  grep -q "running; skip" "$LOG" \
    && echo "ok: busy run skipped" || { echo "FAIL: busy run not skipped"; fail=1; }
  sleep 1
  start_count="$(grep -c 'Phase .* started\.' "$LOG" || true)"
  [ "$start_count" = 1 ] \
    && echo "ok: one start notification logged" || { echo "FAIL: expected one start notification, got $start_count"; fail=1; }
  grep -q '\[clio\]' "$LOG" \
    && { echo "FAIL: old notification prefix remains"; fail=1; } \
    || echo "ok: notification prefix removed"

  wait_phase_window_gone
  grep -q "Phase .* has completed\." "$LOG" \
    && echo "ok: completion notification logged" || { echo "FAIL: completion notification missing"; fail=1; }

  # The whole point of the change: the session outlives the phase.
  tmux_session_exists \
    && echo "ok: session survives phase completion" \
    || { echo "FAIL: session died with the phase"; fail=1; }
  tmux_window_exists \
    && { echo "FAIL: phase window still present after completion"; fail=1; } \
    || echo "ok: phase window closed on completion"
  tmux list-windows -t "$SESSION" -F '#{window_name}' 2>/dev/null | grep -qx -- idle \
    && echo "ok: idle window survives phase" || { echo "FAIL: idle window gone after phase"; fail=1; }
  case "$(title_of)" in
    *"done"*) echo "ok: completion title set ($(title_of))" ;;
    *) echo "FAIL: completion title not set, got '$(title_of)'"; fail=1 ;;
  esac
  # An idle session must not block the next tick. Count skips before and after
  # rather than grepping the whole log: an earlier legitimate skip (while the
  # first phase ran) is still in there and would mask a real regression.
  skips_before="$(grep -c 'phase window is running; skip' "$LOG" || true)"
  drive --self-test || true
  skips_after="$(grep -c 'phase window is running; skip' "$LOG" || true)"
  if [ "$skips_after" -gt "$skips_before" ]; then
    echo "FAIL: idle session blocked the line"; fail=1
  else
    echo "ok: idle session does not block the line"
  fi
  wait_phase_window_gone

  # Exercise the stall path without waiting for the real threshold. Use this
  # shell as the live process so the test does not race the short stub run.
  old_stale_after_sec="$STALE_AFTER_SEC"
  stall_test_phase=100000
  printf '%s\n' "$stall_test_phase" >"$CURRENT"
  printf '%s\n' "$$" >"$PIDFILE"
  : >"$RUN_DIR/session-$stall_test_phase.log"
  STALE_AFTER_SEC=0
  sleep 1
  check_stall
  stall_count="$(grep -c 'Phase .* looks stalled\.' "$LOG" || true)"
  [ "$stall_count" = 1 ] && [ -f "$STALL" ] \
    && echo "ok: one stall notification logged" || { echo "FAIL: expected one stall notification, got $stall_count"; fail=1; }
  check_stall
  stall_count_after="$(grep -c 'Phase .* looks stalled\.' "$LOG" || true)"
  [ "$stall_count_after" = "$stall_count" ] \
    && echo "ok: stall notification is not repeated" || { echo "FAIL: stall notification repeated"; fail=1; }
  rm -f "$STALL" "$CURRENT" "$PIDFILE"
  STALE_AFTER_SEC="$old_stale_after_sec"

  DRIVER_STUB_RC=1; export DRIVER_STUB_RC
  rm -f "$HALT"
  drive --self-test || true
  wait_phase_window_gone
  [ -f "$HALT" ] \
    && echo "ok: halt marker written" || { echo "FAIL: halt marker missing"; fail=1; }
  grep -q "Phase .* stopped\." "$LOG" \
    && echo "ok: halt notification logged" || { echo "FAIL: halt notification missing"; fail=1; }
  case "$(title_of)" in
    *HALTED*) echo "ok: halt title set ($(title_of))" ;;
    *) echo "FAIL: halt title not set, got '$(title_of)'"; fail=1 ;;
  esac

  drive --self-test || true
  grep -q "refusing to advance" "$LOG" \
    && echo "ok: refuses to advance while halted" || { echo "FAIL: advanced while halted"; fail=1; }
  tmux_window_exists \
    && { echo "FAIL: opened a phase window while halted"; fail=1; } \
    || echo "ok: no phase window opened while halted"

  # Signal stop: Ctrl-C reaches the trap, which halts and notifies. This is the
  # case that proves Ctrl-C is aimed at the phase window: the idle window is
  # still there, and a session-scoped send-keys would have hit it instead.
  rm -f "$HALT"
  DRIVER_STUB_RC=0; DRIVER_STUB_SLEEP=20; export DRIVER_STUB_RC DRIVER_STUB_SLEEP
  drive --self-test || true
  sleep 0.5
  stop || true
  wait_phase_window_gone
  [ -f "$HALT" ] \
    && echo "ok: stop wrote halt marker" || { echo "FAIL: stop marker missing"; fail=1; }
  grep -q "Phase .* stopped by signal\." "$LOG" \
    && echo "ok: stop notification logged" || { echo "FAIL: stop notification missing"; fail=1; }
  tmux_session_exists \
    && echo "ok: session survives an operator stop" \
    || { echo "FAIL: session died on operator stop"; fail=1; }

  # Coordination failure: the normal driver path must refuse before tmux launch.
  old_repo="$REPO"; old_priv="$PRIV"; old_wf="$WF"
  old_run_dir="$RUN_DIR"; old_lock="$LOCK"; old_halt="$HALT"; old_stall="$STALL"
  old_current="$CURRENT"; old_pid="$PIDFILE"; old_notify_broken="$NOTIFY_BROKEN"
  old_log="$LOG"; old_session="$SESSION"
  coord_root="$tmp/coordination-failure-root"
  coord_run="$tmp/coordination-failure-run"
  mkdir -p "$coord_root" "$coord_run"
  REPO="$coord_root"; PRIV="private/clio-private"; WF="$coord_run"
  RUN_DIR="$coord_run"
  LOCK="$RUN_DIR/driver.lock"; HALT="$RUN_DIR/halted"; STALL="$RUN_DIR/stalled"
  CURRENT="$RUN_DIR/current"; PIDFILE="$RUN_DIR/pid"
  NOTIFY_BROKEN="$RUN_DIR/notify-broken"; LOG="$RUN_DIR/driver.log"
  SESSION="ar-driver-coord-failure-$$"
  drive || true
  if grep -q "coordination checkout sync failed" "$LOG" \
      && ! tmux_window_exists 2>/dev/null; then
    echo "ok: coordination failure refuses launch"; coord_fail_ok=1
  else
    echo "FAIL: coordination failure did not refuse launch"; coord_fail_ok=0; fail=1
  fi
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  REPO="$old_repo"; PRIV="$old_priv"; WF="$old_wf"
  RUN_DIR="$old_run_dir"; LOCK="$old_lock"; HALT="$old_halt"; STALL="$old_stall"
  CURRENT="$old_current"; PIDFILE="$old_pid"; NOTIFY_BROKEN="$old_notify_broken"
  LOG="$old_log"; SESSION="$old_session"

  # Orphan: killing the phase window does not signal the pane, so a live
  # recorded PID with no phase window must halt instead of starting a second
  # concurrent run. The session deliberately SURVIVES the kill here, which is
  # what makes this the real test: a session-scoped existence check would see a
  # live session, wrongly conclude work is in flight, and skip.
  rm -f "$HALT"
  drive --self-test || true
  sleep 0.5
  tmux kill-window -t "$SESSION:$TMUX_PHASE_WINDOW" 2>/dev/null || true
  sleep 0.3
  tmux_session_exists \
    && echo "ok: session outlives a killed phase window (orphan precondition)" \
    || echo "note: session gone; orphan test ran without the persistent-session case"
  drive --self-test || true
  grep -q "orphaned run detected" "$LOG" \
    && echo "ok: orphan detected" || { echo "FAIL: orphan not detected"; fail=1; }
  [ -f "$HALT" ] \
    && echo "ok: orphan halts the line" || { echo "FAIL: orphan did not halt"; fail=1; }
  [ -f "$PIDFILE" ] && kill -9 "$(cat "$PIDFILE")" 2>/dev/null || true

  # A session outlives every phase, so it is created once and reused forever.
  # That means a settings change, or a hand-made session, would otherwise keep
  # whatever size it was born with. Assert the reconcile path fixes that.
  tmux resize-window -t "$SESSION:$TMUX_IDLE_WINDOW" -x 100 -y 30 2>/dev/null || true
  idle_geom_stale="$(tmux display-message -p -t "$SESSION:$TMUX_IDLE_WINDOW" \
    '#{window_width}x#{window_height}' 2>/dev/null || true)"
  tmux_session_ensure
  idle_geom="$(tmux display-message -p -t "$SESSION:$TMUX_IDLE_WINDOW" \
    '#{window_width}x#{window_height}' 2>/dev/null || true)"
  if [ "$idle_geom" = "${TMUX_WIDTH}x${TMUX_HEIGHT}" ]; then
    echo "ok: idle window reconciled ${idle_geom_stale} -> ${idle_geom}"
  else
    echo "FAIL: idle window stuck at ${idle_geom:-gone}, want ${TMUX_WIDTH}x${TMUX_HEIGHT}"; fail=1
  fi

  # The stage-title hook is a GATING pre_step hook: a nonzero exit stops the
  # run. These assertions exist to fail loudly if that ever changes.
  title_hook="$SCRIPTS/pipeline/tmux_title.sh"
  if [ -f "$title_hook" ]; then
    hook_sess="ar-hook-selftest-$$"
    tmux new-session -d -s "$hook_sess" -x 80 -y 24 -n phase 'sleep 30' 2>/dev/null || true
    hook_rc=0
    for hook_step in developer adversary remediator approver finalize; do
      GLIDE_STEP="$hook_step" CLIO_TMUX_SESSION="$hook_sess" \
        bash "$title_hook" >/dev/null 2>&1 || hook_rc=$?
    done
    [ "$hook_rc" -eq 0 ] \
      && echo "ok: stage hook exits 0 for all five steps" \
      || { echo "FAIL: stage hook exited $hook_rc"; fail=1; }
    hook_title="$(tmux show-option -t "$hook_sess" -v set-titles-string 2>/dev/null || true)"
    case "$hook_title" in
      *finalize*) echo "ok: stage hook set the last title ($hook_title)" ;;
      *) echo "FAIL: stage hook title unexpected: '$hook_title'"; fail=1 ;;
    esac
    hook_win="$(tmux list-windows -t "$hook_sess" -F '#{window_name}' 2>/dev/null | tail -1)"
    case "$hook_win" in
      *finalize*) echo "ok: stage hook renamed the phase window ($hook_win)" ;;
      *) echo "FAIL: stage hook window name unexpected: '$hook_win'"; fail=1 ;;
    esac
    # The rename must not make the window unfindable: the driver looks it up by
    # ID, so a display label like "phase adversary" cannot break a later
    # interrupt, pipe-pane, or geometry read.
    hook_wid="$(tmux list-windows -t "$hook_sess" -F '#{window_id} #{window_name}' 2>/dev/null \
      | awk '$2 ~ /^phase/ { print $1 }')"
    [ -n "$hook_wid" ] \
      && echo "ok: renamed phase window still resolvable by id ($hook_wid)" \
      || { echo "FAIL: renamed phase window is no longer resolvable"; fail=1; }
    # Missing session and missing step must both be silent and harmless.
    GLIDE_STEP=developer CLIO_TMUX_SESSION="ar-no-such-session-$$" \
      bash "$title_hook" >/dev/null 2>&1 \
      && echo "ok: stage hook tolerates a missing session" \
      || { echo "FAIL: stage hook failed on a missing session"; fail=1; }
    GLIDE_STEP="" CLIO_TMUX_SESSION="$hook_sess" \
      bash "$title_hook" >/dev/null 2>&1 \
      && echo "ok: stage hook tolerates an empty step" \
      || { echo "FAIL: stage hook failed on an empty step"; fail=1; }
    tmux kill-session -t "$hook_sess" 2>/dev/null || true
  else
    echo "FAIL: stage hook script missing at $title_hook"; fail=1
  fi

  tmux kill-session -t "$SESSION" 2>/dev/null || true
  tmux kill-session -t "ar-hook-selftest-$$" 2>/dev/null || true
  tmux kill-session -t "ar-no-such-session-$$" 2>/dev/null || true
  rm -rf "$tmp"
  echo "driver self-test: $([ "$fail" = 0 ] && echo pass || echo FAIL)"
  return "$fail"
}

check() {
  local name bin
  for name in tmux hermes; do
    if bin="$(command -v "$name")"; then echo "$name: $bin"; else echo "$name: MISSING"; fi
  done
  if "$PYTHON" -c 'import yaml' >/dev/null 2>&1; then
    echo "python3: $PYTHON (PyYAML OK)"
  else
    echo "python3: $PYTHON (PyYAML MISSING - runner.py will fail on import)"
  fi
  if command -v flock >/dev/null 2>&1; then
    echo "flock: $(command -v flock)"
  else
    echo "flock: absent (double-start guard falls back to the tmux session check)"
  fi
  if hermes -p "$PROFILE" send --list >/dev/null 2>&1; then
    echo "profile '$PROFILE': usable for send"
  else
    echo "profile '$PROFILE': NOT usable here (need a local Hermes profile with Discord)"
  fi
  [ -f "$WF/.driver.env" ] && echo "env file: present" || echo "env file: none (defaults in use)"
  echo "heartbeat: ${HEARTBEAT_URL:-unset}"
  echo "stall threshold: ${STALE_AFTER_SEC}s"
  echo "tmux geometry: ${TMUX_WIDTH}x${TMUX_HEIGHT} (pinned with window-size manual; a display attached with -r cannot change it)"
  if tmux_session_exists; then
    echo "tmux session '$SESSION': present (persistent, outlives every phase)"
    tmux_window_exists \
      && echo "  phase window: running, $(tmux_phase_window_geometry)" \
      || echo "  phase window: absent (idle)"
    echo "  title: $(tmux show-option -t "$SESSION" -v set-titles-string 2>/dev/null || echo '(unset)')"
    echo "  attach read-only: tmux attach -t $SESSION -r"
  else
    echo "tmux session '$SESSION': not created yet (created on the next launch)"
  fi
  "$PYTHON" "$SCRIPTS/pipeline/next_phase.py" --self-test
  "$PYTHON" "$SCRIPTS/pipeline/phase_reservations.py" --self-test
}

case "${1:-}" in
  --session)
    [ "$#" -eq 3 ] || { echo "usage: phase-driver.sh --session <N> <phase-file>" >&2; exit 2; }
    run_session "$2" "$3"
    ;;
  --check)     check ;;
  --self-test) driver_self_test ;;
  --stop)      stop ;;
  --dry-run)   DRY_RUN=1; drive ;;
  ""|--drive)  drive ;;
  *)
    echo "usage: phase-driver.sh [--dry-run|--check|--self-test|--stop] | --session <N> <phase-file>" >&2
    exit 2
    ;;
esac
